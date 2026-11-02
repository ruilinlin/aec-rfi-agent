"""Low-level search queries against the chunks and documents tables.

Two independent signals over the same corpus:
  - dense_search: pgvector cosine distance over chunk embeddings;
  - keyword_search: Postgres full-text search over the generated tsv column.
Both return the same row shape so hybrid.py can fuse them by chunk id.
"""

import json

import psycopg
from psycopg.rows import dict_row

ALLOWED_FILTERS = ("doc_type", "section_code", "revision")
# Two parallel chunkings of the same corpus: section-aware (default) and the
# fixed-size baseline. Table names are whitelisted, never interpolated raw.
ALLOWED_TABLES = ("chunks", "chunks_fixed")


def _select(table: str) -> str:
    if table not in ALLOWED_TABLES:
        raise ValueError(f"unsupported table: {table}")
    return f"""
    SELECT c.id, c.document_id, c.section_path, c.page, c.text,
           d.doc_type, d.section_code, d.revision
    FROM {table} c
    JOIN documents d ON d.id = c.document_id
"""


def _filter_sql(filters: dict | None) -> tuple[str, dict]:
    """Build parameterized AND clauses for the allowed document filters."""
    if not filters:
        return "", {}
    unknown = set(filters) - set(ALLOWED_FILTERS)
    if unknown:
        raise ValueError(f"unsupported filters: {sorted(unknown)}")
    clauses = []
    params = {}
    for field in ALLOWED_FILTERS:
        if filters.get(field) is not None:
            clauses.append(f"AND d.{field} = %({field})s")
            params[field] = filters[field]
    return " ".join(clauses), params


def dense_search(
    conn: psycopg.Connection,
    embedding: list[float],
    k: int = 50,
    filters: dict | None = None,
    table: str = "chunks",
) -> list[dict]:
    """Top-k chunks by cosine distance to the query embedding."""
    where, params = _filter_sql(filters)
    sql = f"""
        {_select(table)}
        WHERE TRUE {where}
        ORDER BY c.embedding <=> %(vec)s::vector
        LIMIT %(k)s
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, {**params, "vec": json.dumps(embedding), "k": k})
        return cur.fetchall()


def keyword_search(
    conn: psycopg.Connection,
    query: str,
    k: int = 50,
    filters: dict | None = None,
    table: str = "chunks",
) -> list[dict]:
    """Top-k chunks by full-text rank against the query words."""
    where, params = _filter_sql(filters)
    sql = f"""
        {_select(table)},
             plainto_tsquery('english', %(q)s) AS tsq
        WHERE c.tsv @@ tsq {where}
        ORDER BY ts_rank(c.tsv, tsq) DESC
        LIMIT %(k)s
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, {**params, "q": query, "k": k})
        return cur.fetchall()
