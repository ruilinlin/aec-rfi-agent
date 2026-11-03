"""Tests for the FastAPI endpoint. The agent graph is faked; no LLM, no DB."""

from fastapi.testclient import TestClient

from src.api.main import app, get_graph
from src.schemas import Citation, CitedResponse, GapReport


class FakeGraph:
    def __init__(self, response):
        self.response = response
        self.last_state = None

    def invoke(self, state):
        self.last_state = state
        return {**state, "response": self.response}


CITED = CitedResponse(
    rfi_id="rfi-1",
    rfi_type="clarification",
    answer="Two coats of epoxy primer are required.",
    citations=[
        Citation(
            chunk_id="UFGS-09-90-00:0042",
            section_code="09 90 00",
            revision="UFGS-2026-08",
            quote_span="two coats of epoxy primer",
        )
    ],
)

GAP = GapReport(rfi_id="rfi-2", reason="no governing requirement found", searched=["14 20 00"])


def _client(response) -> tuple[TestClient, FakeGraph]:
    fake = FakeGraph(response)
    app.dependency_overrides[get_graph] = lambda: fake
    return TestClient(app), fake


def teardown_function():
    app.dependency_overrides.clear()


def test_rfi_returns_cited_response_with_citations():
    client, fake = _client(CITED)
    resp = client.post("/rfi", json={"id": "rfi-1", "question": "What primer is required?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"].startswith("Two coats")
    assert body["citations"][0]["section_code"] == "09 90 00"
    assert fake.last_state["rfi"].question == "What primer is required?"


def test_rfi_returns_gap_report_when_evidence_is_missing():
    client, _ = _client(GAP)
    resp = client.post("/rfi", json={"id": "rfi-2", "question": "Elevator capacity?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["reason"] == "no governing requirement found"
    assert "answer" not in body


def test_rfi_returns_422_when_question_is_missing():
    client, _ = _client(CITED)
    resp = client.post("/rfi", json={"id": "rfi-3"})
    assert resp.status_code == 422


def test_rfi_accepts_optional_references():
    client, fake = _client(CITED)
    resp = client.post(
        "/rfi",
        json={"id": "rfi-4", "question": "Primer?", "references": ["09 90 00"]},
    )
    assert resp.status_code == 200
    assert fake.last_state["rfi"].references == ["09 90 00"]


def test_health_endpoint():
    client, _ = _client(CITED)
    assert client.get("/health").json() == {"status": "ok"}
