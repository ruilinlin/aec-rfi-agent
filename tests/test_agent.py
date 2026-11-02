"""Unit tests for the agent nodes and LLM reply parsing (no network, no DB).

LLM calls are monkeypatched: nodes must behave correctly around whatever
JSON the model returns, including hallucinated chunk ids.
"""

import pytest

from src.agent import llm, nodes
from src.agent.llm import parse_json_reply
from src.schemas import RFIRequest


def test_parse_json_reply_handles_markdown_fences():
    reply = 'Here you go:\n```json\n{"rfi_type": "conflict", "references": []}\n```'
    assert parse_json_reply(reply) == {"rfi_type": "conflict", "references": []}


def test_parse_json_reply_handles_bare_json():
    assert parse_json_reply('{"answer": "ok", "citations": []}') == {
        "answer": "ok",
        "citations": [],
    }


def test_parse_json_reply_raises_on_prose_only():
    with pytest.raises(ValueError):
        parse_json_reply("I cannot answer that question.")


def _rfi(**kwargs) -> RFIRequest:
    defaults = {"id": "rfi-test", "question": "What primer is required on interior steel?"}
    return RFIRequest(**{**defaults, **kwargs})


def test_classify_merges_llm_references_with_request_references(monkeypatch):
    monkeypatch.setattr(
        llm,
        "complete_json",
        lambda system, user, **kw: {"rfi_type": "clarification", "references": ["09 90 00"]},
    )
    update = nodes.classify({"rfi": _rfi(references=["05 12 00", "09 90 00"])})
    assert update["rfi_type"] == "clarification"
    assert update["references"] == ["05 12 00", "09 90 00"]  # deduplicated, order kept


CHUNKS = [
    {
        "id": "UFGS-09-90-00:0042",
        "section_code": "09 90 00",
        "section_path": "PART 2 > 2.1",
        "revision": "UFGS-2026-08",
        "text": "Apply two coats of epoxy primer to interior steel surfaces.",
    }
]


def test_draft_builds_citations_and_drops_hallucinated_chunk_ids(monkeypatch):
    monkeypatch.setattr(
        llm,
        "complete_json",
        lambda system, user, **kw: {
            "answer": "Two coats of epoxy primer are required.",
            "citations": [
                {"chunk_id": "UFGS-09-90-00:0042", "quote_span": "two coats of epoxy primer"},
                {"chunk_id": "UFGS-99-99-99:0001", "quote_span": "made up"},
            ],
        },
    )
    update = nodes.draft({"rfi": _rfi(), "rfi_type": "clarification", "chunks": CHUNKS})
    response = update["response"]
    assert len(response.citations) == 1  # hallucinated id was dropped
    citation = response.citations[0]
    assert citation.chunk_id == "UFGS-09-90-00:0042"
    assert citation.section_code == "09 90 00"
    assert citation.revision == "UFGS-2026-08"
    assert response.rfi_id == "rfi-test"


def test_draft_rejects_output_with_zero_valid_citations(monkeypatch):
    monkeypatch.setattr(
        llm,
        "complete_json",
        lambda system, user, **kw: {
            "answer": "Something plausible but unsupported.",
            "citations": [{"chunk_id": "UFGS-99-99-99:0001", "quote_span": "made up"}],
        },
    )
    with pytest.raises(ValueError, match="zero valid citations"):
        nodes.draft({"rfi": _rfi(), "rfi_type": "clarification", "chunks": CHUNKS})
