"""Graph-trace integration: stages recorded in pipeline order, and the
eval path (no active trace) stays completely unaffected. Nodes are stubbed;
no LLM, no DB."""

from src.agent import graph as graph_module
from src.agent.trace import record_usage
from src.schemas import Citation, CitedResponse


def _stub_nodes(monkeypatch):
    def classify(state):
        record_usage("claude-sonnet-5", 100, 10)
        return {"rfi_type": "clarification", "references": []}

    def retrieve(state):
        record_usage("voyage-3.5", 50, 0)
        return {"chunks": []}

    def cross_check(state):
        return {"superseded_notes": []}

    def draft(state):
        return {"draft_answer": "answer", "draft_citations": []}

    def verify(state):
        response = CitedResponse(
            rfi_id=state["rfi"].id,
            rfi_type=state["rfi_type"],
            answer="answer",
            citations=[
                Citation(chunk_id="c:1", section_code="09 90 00",
                         revision="UFGS-2026-08", quote_span="q")
            ],
        )
        return {"response": response}

    for name, fn in [("classify", classify), ("retrieve", retrieve),
                     ("cross_check", cross_check), ("draft", draft), ("verify", verify)]:
        monkeypatch.setattr(graph_module, name, fn)


def test_run_rfi_records_stages_in_pipeline_order(monkeypatch):
    _stub_nodes(monkeypatch)
    response = graph_module.run_rfi("What primer is required?", rfi_id="rfi-t")
    stages = response.usage.stages
    assert [s.stage for s in stages] == ["classify", "retrieve", "cross_check", "draft", "verify"]
    by_name = {s.stage: s for s in stages}
    assert (by_name["classify"].input_tokens, by_name["classify"].model) == (100, "claude-sonnet-5")
    assert by_name["retrieve"].model == "voyage-3.5"
    assert by_name["cross_check"].input_tokens == 0 and by_name["cross_check"].model is None
    assert response.usage.total_cost_usd > 0


def test_graph_invoked_without_trace_is_unaffected(monkeypatch):
    # The eval harness invokes the compiled graph directly, with no trace_run:
    # record_usage calls inside nodes must be dropped and usage must stay None.
    _stub_nodes(monkeypatch)
    from src.schemas import RFIRequest

    state = graph_module.build_graph().invoke(
        {"rfi": RFIRequest(id="rfi-e", question="q")}
    )
    assert state["response"].usage is None
