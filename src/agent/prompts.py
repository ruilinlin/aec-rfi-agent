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
    lines = [f"RFI {rfi.id} (type: {state['rfi_type']}):", rfi.question, "", "Evidence chunks:"]
    for chunk in state["chunks"]:
        lines.append(
            f"--- chunk_id: {chunk['id']} | section {chunk['section_code']} "
            f"| {chunk['section_path']} | revision {chunk['revision']}"
        )
        lines.append(chunk["text"][:2000])
    return "\n".join(lines)
