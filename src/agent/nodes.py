"""Agent graph nodes: classify -> retrieve -> cross_check -> draft -> verify.

classify, draft and verify call the LLM; retrieve and cross_check are
deterministic. What counts as evidence is decided in code: revision
governance (cross_check), citation id validity (draft), and verbatim-quote
checking (verify) are never delegated to the model.
"""

import os
import re

import psycopg

from src.agent import llm, prompts
from src.ingest.index import embed_texts
from src.retrieval.hybrid import hybrid_search
from src.schemas import Citation, CitedResponse, GapReport

RETRIEVE_K = 10
RETRIEVE_K_PER_REFERENCE = 5
CLOSEST_MATCHES = 3


def classify(state: dict) -> dict:
    """LLM triage: RFI type plus every MasterFormat code the RFI mentions."""
    rfi = state["rfi"]
    data = llm.complete_json(prompts.CLASSIFY_SYSTEM, prompts.classify_user(rfi))
    extracted = [ref.strip() for ref in data.get("references", [])]
    references = list(dict.fromkeys([*rfi.references, *extracted]))
    return {"rfi_type": data["rfi_type"], "references": references}


def retrieve(state: dict) -> dict:
    """Hybrid search, plus a filtered pass per referenced section code.

    The question is embedded once and reused across passes; referenced codes
    go through the section_code metadata filter (chunk text does not contain
    its own section number, so keyword search cannot find codes).
    """
    question = state["rfi"].question
    table = state.get("retrieval_table", "chunks")
    embedding = embed_texts([question], input_type="query")[0]
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        rows = hybrid_search(conn, question, k=RETRIEVE_K, embedding=embedding, table=table)
        seen = {row["id"] for row in rows}
        for code in state["references"]:
            filtered = hybrid_search(
                conn,
                question,
                k=RETRIEVE_K_PER_REFERENCE,
                filters={"section_code": code},
                embedding=embedding,
                table=table,
            )
            for row in filtered:
                if row["id"] not in seen:
                    rows.append(row)
                    seen.add(row["id"])
    return {"chunks": rows}


def _superseded_doc_ids(conn: psycopg.Connection, doc_ids: set[str]) -> dict[str, str]:
    """Map each superseded document id to the revision that replaces it."""
    rows = conn.execute(
        """
        SELECT old.id, newer.revision
        FROM documents newer
        JOIN documents old ON newer.supersedes_id = old.id
        WHERE old.id = ANY(%s)
        """,
        (list(doc_ids),),
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def partition_superseded(
    chunks: list[dict], superseded: dict[str, str]
) -> tuple[list[dict], list[str]]:
    """Split chunks into governing evidence and superseded notes.

    Superseded chunks never remain as evidence; each (section, path) yields
    one human-readable note so the draft can flag the stale reference.
    """
    governing: list[dict] = []
    notes: list[str] = []
    noted: set[tuple[str, str]] = set()
    for chunk in chunks:
        newer_revision = superseded.get(chunk["document_id"])
        if newer_revision is None:
            governing.append(chunk)
            continue
        key = (chunk["section_code"], chunk["section_path"])
        if key not in noted:
            noted.add(key)
            notes.append(
                f"{chunk['section_code']} {chunk['section_path']} rev {chunk['revision']} "
                f"is superseded by rev {newer_revision}"
            )
    return governing, notes


def cross_check(state: dict) -> dict:
    """Deterministic revision governance: keep only governing-revision chunks."""
    chunks = state["chunks"]
    if not chunks:
        return {"superseded_notes": []}
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        superseded = _superseded_doc_ids(conn, {c["document_id"] for c in chunks})
    governing, notes = partition_superseded(chunks, superseded)
    return {"chunks": governing, "superseded_notes": notes}


def draft(state: dict) -> dict:
    """LLM drafts the response; code keeps only citations of provided chunks.

    A draft with zero valid citations is not an error here: verify turns it
    into a GapReport.
    """
    data = llm.complete_json(prompts.DRAFT_SYSTEM, prompts.draft_user(state), max_tokens=4096)

    rows_by_id = {chunk["id"]: chunk for chunk in state["chunks"]}
    citations = []
    for raw in data.get("citations", []):
        row = rows_by_id.get(raw.get("chunk_id"))
        if row is None:
            continue  # the model cited an id it was never given; drop it
        citations.append(
            Citation(
                chunk_id=row["id"],
                section_code=row["section_code"],
                revision=row["revision"],
                quote_span=raw.get("quote_span", ""),
            )
        )
    return {"draft_answer": data.get("answer", ""), "draft_citations": citations}


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def quote_verbatim(quote: str, chunk_text: str) -> bool:
    """True when the quote appears in the chunk, ignoring line-wrap whitespace.

    PDF extraction wraps lines mid-sentence, so raw substring checks fail on
    genuinely verbatim quotes; both sides are whitespace-normalized first.
    """
    return bool(quote.strip()) and _normalize_ws(quote) in _normalize_ws(chunk_text)


def verify(state: dict) -> dict:
    """Validate the draft; emit CitedResponse or a GapReport.

    Two gates, strictest first:
    1. deterministic: every citation's quote_span must appear verbatim
       (whitespace-normalized) in its cited chunk;
    2. LLM review: does the surviving evidence actually settle the question?
       Unsupported claims are removed from the answer in the same pass.
    """
    rfi = state["rfi"]
    chunks_by_id = {chunk["id"]: chunk for chunk in state["chunks"]}
    quote_valid = [
        c
        for c in state["draft_citations"]
        if c.chunk_id in chunks_by_id and quote_verbatim(c.quote_span, chunks_by_id[c.chunk_id]["text"])
    ]

    if quote_valid:
        data = llm.complete_json(
            prompts.VERIFY_SYSTEM, prompts.verify_user(state, quote_valid), max_tokens=4096
        )
        supported_ids = set(data.get("supported_chunk_ids", []))
        final = [c for c in quote_valid if c.chunk_id in supported_ids]
        if data.get("verdict") == "supported" and final and data.get("revised_answer"):
            response = CitedResponse(
                rfi_id=rfi.id,
                rfi_type=state["rfi_type"],
                answer=data["revised_answer"],
                citations=final,
                superseded_notes=state.get("superseded_notes", []),
            )
            return {"response": response}
        reason = data.get("reason", "the cited evidence does not settle the question")
    else:
        reason = "no citation survived verbatim quote verification"

    closest = [
        Citation(
            chunk_id=chunk["id"],
            section_code=chunk["section_code"],
            revision=chunk["revision"],
            quote_span="",
        )
        for chunk in state["chunks"][:CLOSEST_MATCHES]
    ]
    searched = sorted({c["section_code"] for c in state["chunks"]} | set(state["references"]))
    report = GapReport(rfi_id=rfi.id, reason=reason, searched=searched, closest_matches=closest)
    return {"response": report}


def finalize_unverified(state: dict) -> dict:
    """Terminal node for the -verify ablation: accept the draft as-is.

    No quote checking, no claim review; only the zero-citation case still
    becomes a GapReport so the output type stays CitedResponse | GapReport.
    """
    rfi = state["rfi"]
    if state["draft_citations"]:
        response = CitedResponse(
            rfi_id=rfi.id,
            rfi_type=state["rfi_type"],
            answer=state["draft_answer"],
            citations=state["draft_citations"],
            superseded_notes=state.get("superseded_notes", []),
        )
        return {"response": response}
    searched = sorted({c["section_code"] for c in state["chunks"]} | set(state["references"]))
    report = GapReport(
        rfi_id=rfi.id, reason="draft produced no valid citations", searched=searched
    )
    return {"response": report}
