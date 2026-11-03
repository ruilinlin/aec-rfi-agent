"""Hybrid retrieval: dense + keyword results fused with Reciprocal Rank Fusion.

RRF scores a chunk by the sum of 1 / (K + rank) over every ranking it appears
in (rank is 1-based). It needs no score calibration between the two signals —
only positions matter — which is why it is the standard fusion for mixing
cosine distances with ts_rank values that live on incomparable scales.

Usage (ad-hoc check from the repo root):
    .venv/bin/python -m src.retrieval.hybrid "minimum dry film thickness"
"""

import os
import sys

import psycopg

from src.ingest.index import embed_texts
from src.retrieval.store import dense_search, keyword_search

RRF_K = 60


def rrf_fuse(rankings: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    """Fuse ranked id lists into {id: score}. Higher score = better."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for position, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + position)
    return scores


def hybrid_search(
    conn: psycopg.Connection,
    question: str,
    k: int = 10,
    filters: dict | None = None,
    fetch_k: int = 50,
    embedding: list[float] | None = None,
    table: str = "chunks",
) -> list[dict]:
    """Embed the question, run both searches, fuse with RRF, return top-k rows.

    fetch_k controls how deep each signal's candidate list goes before fusion;
    deeper lists give RRF more overlap evidence at the cost of two bigger reads.
    Pass a precomputed query embedding to reuse it across several calls.
    """
    if embedding is None:
        embedding = embed_texts([question], input_type="query")[0]
    dense = dense_search(conn, embedding, fetch_k, filters, table=table)
    keyword = keyword_search(conn, question, fetch_k, filters, table=table)

    rows_by_id = {row["id"]: row for row in dense + keyword}
    scores = rrf_fuse([[r["id"] for r in dense], [r["id"] for r in keyword]])
    top_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:k]
    return [{**rows_by_id[cid], "rrf_score": scores[cid]} for cid in top_ids]


def main() -> int:
    from dotenv import load_dotenv

    if len(sys.argv) < 2:
        print('usage: python -m src.retrieval.hybrid "your question"')
        return 2
    load_dotenv()
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        for row in hybrid_search(conn, sys.argv[1], k=5):
            print(
                f"{row['rrf_score']:.4f}  {row['document_id']}  "
                f"{row['section_path']}  (p.{row['page']})"
            )
            print(f"        {row['text'][:100].replace(chr(10), ' ')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
