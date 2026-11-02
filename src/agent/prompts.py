"""Prompt templates for the agent nodes. All replies must be a single JSON object."""

CLASSIFY_SYSTEM = """\
You triage construction RFIs (Requests for Information) sent by contractors.

Return ONLY a JSON object, no other text:
{"rfi_type": "clarification" | "conflict" | "superseded_ref" | "substitution" | "other",
 "references": ["<every MasterFormat section code mentioned in the RFI, e.g. 09 90 00>"]}

rfi_type meanings:
- clarification: the documents are unclear or silent on a detail
- conflict: two documents (or two clauses) appear to contradict each other
- superseded_ref: the RFI cites a revision or document that may be outdated
- substitution: the contractor proposes an alternative product or method
- other: anything else
"""


def classify_user(rfi) -> str:
    return f"RFI {rfi.id}:\n{rfi.question}"


DRAFT_SYSTEM = """\
You draft a response to a construction RFI for a licensed professional to review.
You are given evidence chunks from the governing project specifications.

Rules:
- Use ONLY the provided evidence chunks. Never invent a requirement.
- Text beginning with "NOTE:" inside a chunk is an instruction to the
  specification editor, not a contract requirement. Never cite NOTE text as
  evidence for a requirement.
- Every claim in the answer must be supported by at least one citation.
- quote_span must be words copied verbatim from the cited chunk.
- Cite only chunk_id values that appear in the evidence list.
- If the evidence only partially answers the question, say exactly what is
  and is not covered, citing what exists.

Return ONLY a JSON object, no other text:
{"answer": "<the drafted RFI response>",
 "citations": [{"chunk_id": "<id>", "quote_span": "<verbatim words from that chunk>"}]}
"""


def draft_user(state: dict) -> str:
    rfi = state["rfi"]
    lines = [f"RFI {rfi.id} (type: {state['rfi_type']}):", rfi.question, ""]
    if state.get("superseded_notes"):
        lines.append("Superseded references (NOT evidence; mention them as notes if relevant):")
        lines.extend(f"- {note}" for note in state["superseded_notes"])
        lines.append("")
    lines.append("Evidence chunks:")
    for chunk in state["chunks"]:
        lines.append(
            f"--- chunk_id: {chunk['id']} | section {chunk['section_code']} "
            f"| {chunk['section_path']} | revision {chunk['revision']}"
        )
        lines.append(chunk["text"][:2000])
    return "\n".join(lines)


VERIFY_SYSTEM = """\
You are a strict reviewer of a drafted construction-RFI response. You get the
RFI question, the drafted answer, and the evidence quotes it cites.

Decide whether the evidence actually settles the question:
- A claim is supported only if a quoted passage states it; general knowledge
  does not count.
- A quote drawn from designer-note text (passages beginning "NOTE:") is an
  instruction to the specification editor, not a contract requirement; claims
  resting only on NOTE text are unsupported.
- If the quotes are about a related but different subject, or the governing
  value the question asks for is blank or absent, the verdict is "gap".
- If supported, produce revised_answer: the drafted answer with every
  unsupported claim removed (keep supported content word-for-word).

Return ONLY a JSON object, no other text:
{"verdict": "supported" | "gap",
 "reason": "<one sentence>",
 "supported_chunk_ids": ["<ids of chunks whose quotes support the revised answer>"],
 "revised_answer": "<answer with unsupported claims removed; empty if gap>"}
"""


def verify_user(state: dict, citations: list) -> str:
    rfi = state["rfi"]
    paths = {chunk["id"]: chunk["section_path"] for chunk in state["chunks"]}
    lines = [f"RFI {rfi.id} (type: {state['rfi_type']}):", rfi.question, "", "Drafted answer:", state["draft_answer"], "", "Cited evidence:"]
    for c in citations:
        lines.append(
            f"--- chunk_id: {c.chunk_id} | section {c.section_code} "
            f"| {paths.get(c.chunk_id, '')} | revision {c.revision}"
        )
        lines.append(f"quote: {c.quote_span}")
    return "\n".join(lines)
