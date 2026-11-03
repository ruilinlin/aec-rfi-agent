"""Baseline B0: LLM only, no retrieval, no citations possible."""

from src.agent import llm

SYSTEM = """\
You answer construction RFIs (Requests for Information) about building
specifications from your own knowledge. Answer as a specifier would.

Return ONLY a JSON object, no other text:
{"answer": "<your answer to the RFI>"}
"""


def run(item: dict) -> dict:
    data = llm.complete_json(SYSTEM, item["question"])
    return {
        "chunks": [],
        "citations": [],
        "abstained": False,
        "answer": data.get("answer", ""),
    }
