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
    citations = update["draft_citations"]
    assert len(citations) == 1  # hallucinated id was dropped
    assert citations[0].chunk_id == "UFGS-09-90-00:0042"
    assert citations[0].section_code == "09 90 00"
    assert citations[0].revision == "UFGS-2026-08"
    assert update["draft_answer"] == "Two coats of epoxy primer are required."


def test_draft_returns_empty_citations_instead_of_raising(monkeypatch):
    # Zero valid citations is not an error at draft time: verify turns it into a GapReport.
    monkeypatch.setattr(
        llm,
        "complete_json",
        lambda system, user, **kw: {
            "answer": "Something plausible but unsupported.",
            "citations": [{"chunk_id": "UFGS-99-99-99:0001", "quote_span": "made up"}],
        },
    )
    update = nodes.draft({"rfi": _rfi(), "rfi_type": "clarification", "chunks": CHUNKS})
    assert update["draft_citations"] == []


def test_partition_superseded_filters_chunks_and_emits_notes():
    chunks = [
        {"id": "new:1", "document_id": "UFGS-09-90-00", "section_code": "09 90 00",
         "section_path": "PART 2 > 2.1", "revision": "UFGS-2026-08", "text": "current"},
        {"id": "old:1", "document_id": "UFGS-09-90-00-PREV", "section_code": "09 90 00",
         "section_path": "PART 2 > 2.1", "revision": "UFGS-2021-02", "text": "stale"},
        {"id": "old:2", "document_id": "UFGS-09-90-00-PREV", "section_code": "09 90 00",
         "section_path": "PART 2 > 2.1", "revision": "UFGS-2021-02", "text": "stale again"},
    ]
    superseded = {"UFGS-09-90-00-PREV": "UFGS-2026-08"}
    governing, notes = nodes.partition_superseded(chunks, superseded)
    assert [c["id"] for c in governing] == ["new:1"]
    assert notes == ["09 90 00 PART 2 > 2.1 rev UFGS-2021-02 is superseded by rev UFGS-2026-08"]


def test_quote_verbatim_ignores_line_wrap_whitespace():
    chunk_text = "submitted \n  for each strength and type\nof concrete"
    assert nodes.quote_verbatim("for each strength and type of concrete", chunk_text)
    assert not nodes.quote_verbatim("for each strength and color", chunk_text)
    assert not nodes.quote_verbatim("   ", chunk_text)  # empty quotes never pass


def _verify_state(**overrides):
    from src.schemas import Citation

    state = {
        "rfi": _rfi(),
        "rfi_type": "clarification",
        "references": [],
        "chunks": CHUNKS,
        "superseded_notes": [],
        "draft_answer": "Two coats of epoxy primer are required.",
        "draft_citations": [
            Citation(
                chunk_id="UFGS-09-90-00:0042",
                section_code="09 90 00",
                revision="UFGS-2026-08",
                quote_span="two coats of epoxy primer",
            )
        ],
    }
    state.update(overrides)
    return state


def test_verify_gap_report_when_no_quote_survives(monkeypatch):
    from src.schemas import Citation, GapReport

    def fail_if_called(*a, **kw):
        raise AssertionError("LLM must not be called when no citation survives")

    monkeypatch.setattr(llm, "complete_json", fail_if_called)
    bad = Citation(
        chunk_id="UFGS-09-90-00:0042",
        section_code="09 90 00",
        revision="UFGS-2026-08",
        quote_span="words that are not in the chunk",
    )
    update = nodes.verify(_verify_state(draft_citations=[bad]))
    report = update["response"]
    assert isinstance(report, GapReport)
    assert "quote verification" in report.reason
    assert report.closest_matches[0].chunk_id == "UFGS-09-90-00:0042"


def test_verify_gap_verdict_from_llm_yields_gap_report(monkeypatch):
    from src.schemas import GapReport

    monkeypatch.setattr(
        llm,
        "complete_json",
        lambda system, user, **kw: {
            "verdict": "gap",
            "reason": "quotes cover elevator feeders, not capacity",
            "supported_chunk_ids": [],
            "revised_answer": "",
        },
    )
    update = nodes.verify(_verify_state())
    report = update["response"]
    assert isinstance(report, GapReport)
    assert report.reason == "quotes cover elevator feeders, not capacity"


def test_verify_supported_verdict_yields_cited_response(monkeypatch):
    from src.schemas import CitedResponse

    monkeypatch.setattr(
        llm,
        "complete_json",
        lambda system, user, **kw: {
            "verdict": "supported",
            "reason": "the quote states the requirement",
            "supported_chunk_ids": ["UFGS-09-90-00:0042"],
            "revised_answer": "Two coats of epoxy primer are required.",
        },
    )
    update = nodes.verify(_verify_state(superseded_notes=["09 90 00 PART 2 rev old superseded"]))
    response = update["response"]
    assert isinstance(response, CitedResponse)
    assert response.answer == "Two coats of epoxy primer are required."
    assert [c.chunk_id for c in response.citations] == ["UFGS-09-90-00:0042"]
    assert response.superseded_notes == ["09 90 00 PART 2 rev old superseded"]
