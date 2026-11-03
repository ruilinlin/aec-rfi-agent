"""Baseline B1: naive RAG - fixed-size chunks, top-k dense retrieval,
an 'answer strictly from the documents' prompt, no revision governance,
no verification."""

import os

import psycopg

from src.agent import llm
from src.ingest.index import embed_texts
from src.retrieval.store import dense_search
from src.schemas import Citation

TOP_K = 8

SYSTEM = """\
You answer construction RFIs strictly from the provided document excerpts.

Return ONLY a JSON object, no other text:
{"answer": "<your answer, based strictly on the documents>",
 "citations": [{"chunk_id": "<id of an excerpt you relied on>", "quote_span": "<supporting words from it>"}]}
"""


def _user(item: dict, rows: list[dict]) -> str:
    lines = [item["question"], "", "Documents:"]
    for row in rows:
        lines.append(f"--- chunk_id: {row['id']} | section {row['section_code']}")
        lines.append(row["text"][:2000])
    return "\n".join(lines)


def run(item: dict) -> dict:
    embedding = embed_texts([item["question"]], input_type="query")[0]
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        rows = dense_search(conn, embedding, k=TOP_K, table="chunks_fixed")
    data = llm.complete_json(SYSTEM, _user(item, rows))

    rows_by_id = {row["id"]: row for row in rows}
    citations = [
        Citation(
            chunk_id=row["id"],
            section_code=row["section_code"],
            revision=row["revision"],
            quote_span=raw.get("quote_span", ""),
        )
        for raw in data.get("citations", [])
        if (row := rows_by_id.get(raw.get("chunk_id"))) is not None
    ]
    return {
        "chunks": rows,
        "citations": [c.model_dump() for c in citations],
        "abstained": False,
        "answer": data.get("answer", ""),
    }
