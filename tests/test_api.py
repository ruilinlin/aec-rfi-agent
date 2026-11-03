"""Tests for the FastAPI endpoint. The agent graph is faked; no LLM, no DB."""

import pytest
from fastapi.testclient import TestClient

from src.api import main as api_main
from src.api.main import MAX_BODY_BYTES, SlidingWindowLimiter, app, create_app, get_graph
from src.schemas import Citation, CitedResponse, GapReport


@pytest.fixture(autouse=True)
def fresh_rate_limiter(monkeypatch):
    """Each test gets its own limiter so /rfi calls never leak across tests."""
    monkeypatch.setattr(
        api_main,
        "rfi_limiter",
        SlidingWindowLimiter(api_main.RFI_RATE_LIMIT, api_main.RFI_RATE_WINDOW_SECONDS),
    )


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


# --- hardening: body-size cap ------------------------------------------------


def test_rfi_returns_413_when_body_exceeds_cap():
    client, fake = _client(CITED)
    resp = client.post(
        "/rfi",
        content=b"x" * (MAX_BODY_BYTES + 1),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 413
    assert fake.last_state is None  # the agent graph was never reached


def test_rfi_rejects_chunked_bodies_without_content_length():
    client, fake = _client(CITED)
    resp = client.post(
        "/rfi",
        content=iter([b"x" * 1024] * 70),  # iterable body -> chunked, no Content-Length
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 413
    assert fake.last_state is None


# --- hardening: rate limit ----------------------------------------------------


def test_rfi_rate_limited_after_window_budget(monkeypatch):
    now = {"t": 0.0}
    monkeypatch.setattr(
        api_main, "rfi_limiter", SlidingWindowLimiter(10, 60.0, clock=lambda: now["t"])
    )
    client, _ = _client(CITED)
    body = {"id": "rfi-rl", "question": "What primer is required?"}
    for _ in range(10):
        assert client.post("/rfi", json=body).status_code == 200
    blocked = client.post("/rfi", json=body)
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    now["t"] = 61.0  # advance past the window without sleeping
    assert client.post("/rfi", json=body).status_code == 200


def test_limiter_isolates_client_keys():
    now = {"t": 0.0}
    limiter = SlidingWindowLimiter(2, 60.0, clock=lambda: now["t"])
    assert limiter.retry_after("1.1.1.1") is None
    assert limiter.retry_after("1.1.1.1") is None
    assert limiter.retry_after("1.1.1.1") is not None  # third hit blocked
    assert limiter.retry_after("2.2.2.2") is None  # other key unaffected


def test_health_is_never_rate_limited():
    client, _ = _client(CITED)
    for _ in range(50):
        assert client.get("/health").status_code == 200


# --- hardening: CORS ----------------------------------------------------------


def test_cors_denied_by_default():
    client, _ = _client(CITED)
    resp = client.options(
        "/rfi",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in resp.headers


def test_cors_allows_configured_origin(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://console.example")
    allowed_app = create_app()
    allowed_app.dependency_overrides[get_graph] = lambda: FakeGraph(CITED)
    client = TestClient(allowed_app)
    resp = client.options(
        "/rfi",
        headers={
            "Origin": "https://console.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.headers["access-control-allow-origin"] == "https://console.example"
