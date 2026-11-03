"""Ingest the downloaded corpus: parse, chunk, embed, upsert into Postgres.

Usage:
    .venv/bin/python -m src.ingest.index --source data/specs

Reads data/MANIFEST.json for the document list, re-ingests every entry whose
local file exists. Idempotent: the document row is upserted and its chunks
are replaced wholesale (delete + insert) on every run.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector

from src.ingest.chunk import chunk_pages, fixed_chunks
from src.ingest.loaders import load_pdf
from src.ingest.metadata import parse_banner
from src.util import ssl_context

ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST_PATH = ROOT / "data" / "MANIFEST.json"

VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
# Free-tier Voyage limits (no payment method): 3 requests/min, 10K tokens/min.
# Batches are sized by estimated tokens (chars/4) and requests are spaced out;
# the 429 backoff in _post_with_retry remains as a safety net.
EMBED_BATCH_TOKEN_BUDGET = 6000
EMBED_REQUEST_DELAY_SECONDS = 40
EMBED_MAX_RETRIES = 8

_last_request_at = 0.0


def _token_batches(texts: list[str]) -> list[list[str]]:
    """Group texts into batches of at most EMBED_BATCH_TOKEN_BUDGET estimated
    tokens (chars/4). A single oversized text still forms its own batch."""
    batches: list[list[str]] = []
    batch: list[str] = []
    budget = 0
    for text in texts:
        estimate = max(1, len(text) // 4)
        if batch and budget + estimate > EMBED_BATCH_TOKEN_BUDGET:
            batches.append(batch)
            batch, budget = [], 0
        batch.append(text)
        budget += estimate
    if batch:
        batches.append(batch)
    return batches


def _throttle() -> None:
    """Space requests EMBED_REQUEST_DELAY_SECONDS apart across all callers."""
    global _last_request_at
    wait = _last_request_at + EMBED_REQUEST_DELAY_SECONDS - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def embed_texts(texts: list[str], input_type: str = "document") -> list[list[float]]:
    """Embed texts with Voyage, batched. input_type 'document' at ingest time
    and 'query' at search time lets the model optimize each side."""
    vectors: list[list[float]] = []
    for batch in _token_batches(texts):
        req = urllib.request.Request(
            VOYAGE_URL,
            data=json.dumps(
                {"model": os.environ["EMBEDDING_MODEL"], "input": batch, "input_type": input_type}
            ).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {os.environ['VOYAGE_API_KEY']}",
            },
        )
        _throttle()
        data = _post_with_retry(req)
        vectors.extend(item["embedding"] for item in data["data"])
    return vectors


def _post_with_retry(req: urllib.request.Request) -> dict:
    """POST with exponential backoff on 429 and on transient network errors.

    429 honors the Retry-After header. URLError (DNS blips, dropped
    connections, timeouts) gets the same backoff: a multi-hour ingest must
    survive a momentary network wobble. Other HTTP errors raise immediately.
    """
    for attempt in range(EMBED_MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, context=ssl_context(), timeout=120) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == EMBED_MAX_RETRIES - 1:
                raise
            retry_after = exc.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else min(2.0**attempt, 60.0)
            print(f"      rate limited (429); retrying in {delay:.0f}s")
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == EMBED_MAX_RETRIES - 1:
                raise
            delay = min(2.0**attempt, 60.0)
            print(f"      network error ({exc.reason if hasattr(exc, 'reason') else exc}); retrying in {delay:.0f}s")
            time.sleep(delay)
    raise RuntimeError("unreachable")


CHUNKERS = {"section": (chunk_pages, "chunks"), "fixed": (fixed_chunks, "chunks_fixed")}


def ingest_document(
    conn: psycopg.Connection, entry: dict, chunker: str = "section"
) -> tuple[int, dict]:
    """Ingest one manifest entry; return (chunks written, parsed banner).

    A document whose stored sha256 already matches the manifest entry is not
    re-embedded (-1 is returned); its banner is still parsed so the
    supersedes pass can run over every document on every run.
    """
    chunk_fn, table = CHUNKERS[chunker]
    pages = load_pdf(ROOT / entry["local_path"])
    banner = parse_banner(pages[0])
    existing = conn.execute(
        "SELECT sha256 FROM documents WHERE id = %s", (entry["id"],)
    ).fetchone()
    has_chunks = conn.execute(
        f"SELECT 1 FROM {table} WHERE document_id = %s LIMIT 1", (entry["id"],)
    ).fetchone()
    if existing and existing[0] == entry["sha256"] and has_chunks:
        return -1, banner
    chunks = chunk_fn(pages)
    vectors = embed_texts([c["text"] for c in chunks])

    conn.execute(
        """
        INSERT INTO documents (id, doc_type, title, source_url, section_code,
                               revision, sha256)
        VALUES (%(id)s, %(doc_type)s, %(title)s, %(url)s, %(section_code)s,
                %(revision)s, %(sha256)s)
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title, source_url = EXCLUDED.source_url,
            revision = EXCLUDED.revision, sha256 = EXCLUDED.sha256
        """,
        {**entry, "revision": banner["revision"]},
    )
    conn.execute(f"DELETE FROM {table} WHERE document_id = %s", (entry["id"],))
    id_prefix = entry["id"] if table == "chunks" else f"{entry['id']}:F"
    with conn.cursor() as cur:
        cur.executemany(
            f"""
            INSERT INTO {table} (id, document_id, section_path, page, text, embedding)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            [
                (f"{id_prefix}:{i:04d}", entry["id"], c["section_path"], c["page"], c["text"], v)
                for i, (c, v) in enumerate(zip(chunks, vectors))
            ],
        )
    return len(chunks), banner


def link_supersedes(conn: psycopg.Connection, banners: dict[str, tuple[str, dict]]) -> int:
    """Point each document at the revision it replaces (DESIGN.md §4).

    The banner states 'Superseding UFGS-<code> (<month> <year>)'; when a
    document with that section_code and revision exists in the corpus, set
    supersedes_id on the newer document. Returns the number of links set.
    """
    linked = 0
    for doc_id, (section_code, banner) in banners.items():
        if not banner.get("supersedes"):
            continue
        result = conn.execute(
            """
            UPDATE documents SET supersedes_id = old.id
            FROM documents old
            WHERE documents.id = %s
              AND old.section_code = %s AND old.revision = %s
              AND old.id <> documents.id
            """,
            (doc_id, section_code, banner["supersedes"]),
        )
        linked += result.rowcount
    return linked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="data/specs", help="corpus directory (informational)")
    parser.add_argument(
        "--chunker",
        default="section",
        choices=sorted(CHUNKERS),
        help="section (default) fills chunks; fixed fills chunks_fixed for baselines",
    )
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    manifest = json.loads(MANIFEST_PATH.read_text())

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        register_vector(conn)
        total = 0
        banners: dict[str, tuple[str, dict]] = {}
        for entry in manifest["documents"]:
            if not (ROOT / entry["local_path"]).exists():
                print(f"skip {entry['id']}: {entry['local_path']} not downloaded")
                continue
            n, banner = ingest_document(conn, entry, args.chunker)
            banners[entry["id"]] = (entry["section_code"], banner)
            if n < 0:
                print(f"skip {entry['id']}: unchanged (sha256 match)")
            else:
                total += n
                print(f"ok   {entry['id']}: {n} chunks")
        linked = link_supersedes(conn, banners)
        print(f"\ningested {total} chunks; {linked} supersedes link(s) set")
    return 0


if __name__ == "__main__":
    sys.exit(main())
