"""Agent graph nodes. Each takes the state and returns a partial update.

classify and draft call the LLM; retrieve is deterministic code. Citation
validity is enforced here in code, not requested in the prompt: a chunk_id
the model was never given is dropped, and a draft with zero valid citations
is rejected outright.
"""

import os

import psycopg

from src.agent import llm, prompts
from src.ingest.index import embed_texts
from src.retrieval.hybrid import hybrid_search
from src.schemas import Citation, CitedResponse

RETRIEVE_K = 10
RETRIEVE_K_PER_REFERENCE = 5


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
    embedding = embed_texts([question], input_type="query")[0]
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        rows = hybrid_search(conn, question, k=RETRIEVE_K, embedding=embedding)
        seen = {row["id"] for row in rows}
        for code in state["references"]:
            filtered = hybrid_search(
                conn,
                question,
                k=RETRIEVE_K_PER_REFERENCE,
                filters={"section_code": code},
                embedding=embedding,
            )
            for row in filtered:
                if row["id"] not in seen:
                    rows.append(row)
                    seen.add(row["id"])
    return {"chunks": rows}


def draft(state: dict) -> dict:
    """LLM drafts the response; code validates every citation against the
    chunks actually provided and rejects uncited output."""
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
    if not citations:
        raise ValueError("draft produced zero valid citations; refusing uncited output")

    response = CitedResponse(
        rfi_id=state["rfi"].id,
        rfi_type=state["rfi_type"],
        answer=data["answer"],
        citations=citations,
    )
    return {"response": response}
