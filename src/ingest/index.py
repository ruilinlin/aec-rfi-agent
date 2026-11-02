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

from src.ingest.chunk import chunk_pages
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
    """POST with exponential backoff on 429, honoring the Retry-After header."""
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
    raise RuntimeError("unreachable")


def ingest_document(conn: psycopg.Connection, entry: dict) -> int:
    """Ingest one manifest entry; return the number of chunks written."""
    pages = load_pdf(ROOT / entry["local_path"])
    banner = parse_banner(pages[0])
    chunks = chunk_pages(pages)
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
    conn.execute("DELETE FROM chunks WHERE document_id = %s", (entry["id"],))
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO chunks (id, document_id, section_path, page, text, embedding)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            [
                (f"{entry['id']}:{i:04d}", entry["id"], c["section_path"], c["page"], c["text"], v)
                for i, (c, v) in enumerate(zip(chunks, vectors))
            ],
        )
    return len(chunks)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="data/specs", help="corpus directory (informational)")
    parser.parse_args()

    load_dotenv(ROOT / ".env")
    manifest = json.loads(MANIFEST_PATH.read_text())

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        register_vector(conn)
        total = 0
        for entry in manifest["documents"]:
            if not (ROOT / entry["local_path"]).exists():
                print(f"skip {entry['id']}: {entry['local_path']} not downloaded")
                continue
            n = ingest_document(conn, entry)
            total += n
            print(f"ok   {entry['id']}: {n} chunks")
        print(f"\ningested {total} chunks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
