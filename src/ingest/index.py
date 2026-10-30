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
import ssl
import sys
import urllib.request
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector

from src.ingest.chunk import chunk_pages
from src.ingest.loaders import load_pdf
from src.ingest.metadata import parse_banner

ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST_PATH = ROOT / "data" / "MANIFEST.json"

VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
EMBED_BATCH_SIZE = 64


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def embed_texts(texts: list[str], input_type: str = "document") -> list[list[float]]:
    """Embed texts with Voyage, batched. input_type 'document' at ingest time
    and 'query' at search time lets the model optimize each side."""
    vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
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
        with urllib.request.urlopen(req, context=_ssl_context(), timeout=120) as resp:
            data = json.loads(resp.read())
        vectors.extend(item["embedding"] for item in data["data"])
    return vectors


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
