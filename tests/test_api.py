"""Tests for the FastAPI endpoint. The agent graph is faked; no LLM, no DB."""

import pytest
from fastapi.testclient import TestClient

from src.api import main as api_main
from src.api.main import MAX_BODY_BYTES, SlidingWindowLimiter, app, create_app, get_graph
from src.schemas import Citation, CitedResponse, GapReport

# The real persist function, for tests that exercise its SQL directly.
REAL_PERSIST_TRACE = api_main.persist_trace


@pytest.fixture(autouse=True)
def no_db_writes(monkeypatch):
    """The suite must never write telemetry to the real database; persisted
    calls are captured here instead. Tests that need the real function use
    REAL_PERSIST_TRACE with a stubbed connection."""
    calls = []
    monkeypatch.setattr(
        api_main, "persist_trace", lambda rfi, response, rfi_type, trace: calls.append(rfi.id)
    )
    yield calls


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


# --- observability ---------------------------------------------------------


def test_rfi_response_carries_usage_summary(no_db_writes):
    client, _ = _client(CITED)
    body = client.post(
        "/rfi", json={"id": "rfi-u", "question": "What primer is required?"}
    ).json()
    assert body["usage"]["total_latency_ms"] >= 0
    assert isinstance(body["usage"]["stages"], list)


def test_gap_report_also_carries_usage(no_db_writes):
    client, _ = _client(GAP)
    body = client.post("/rfi", json={"id": "rfi-g", "question": "Elevator capacity?"}).json()
    assert "reason" in body and "usage" in body


def test_rfi_persists_telemetry_once_per_request(no_db_writes):
    client, _ = _client(CITED)
    client.post("/rfi", json={"id": "rfi-p", "question": "What primer is required?"})
    assert no_db_writes == ["rfi-p"]


def test_rate_limited_requests_persist_nothing(monkeypatch, no_db_writes):
    monkeypatch.setattr(api_main, "rfi_limiter", SlidingWindowLimiter(0, 60.0))
    client, _ = _client(CITED)
    assert client.post("/rfi", json={"id": "rfi-x", "question": "q"}).status_code == 429
    assert no_db_writes == []


def test_persist_failure_never_breaks_the_answer(monkeypatch, no_db_writes):
    def boom(conninfo, *a, **kw):
        raise RuntimeError("db down")

    monkeypatch.setattr(api_main, "persist_trace", REAL_PERSIST_TRACE)
    monkeypatch.setattr(api_main.psycopg, "connect", boom)
    client, _ = _client(CITED)
    resp = client.post("/rfi", json={"id": "rfi-f", "question": "What primer is required?"})
    assert resp.status_code == 200  # telemetry failure is logged, not surfaced


class StubConnection:
    """Records every execute/executemany; works as a context manager."""

    def __init__(self):
        self.executed = []
        self.many = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.executed.append((" ".join(sql.split()), params))

    def cursor(self):
        return self

    def executemany(self, sql, rows):
        self.many.append((" ".join(sql.split()), list(rows)))


def _usage_two_stages():
    from src.schemas import UsageStage, UsageSummary

    return UsageSummary(
        total_latency_ms=1500,
        total_cost_usd=0.012,
        stages=[
            UsageStage(stage="classify", latency_ms=500, input_tokens=100,
                       output_tokens=10, cost_usd=0.002, model="claude-sonnet-5"),
            UsageStage(stage="draft", latency_ms=1000, input_tokens=900,
                       output_tokens=80, cost_usd=0.010, model="claude-sonnet-5"),
        ],
    )


def test_persist_trace_writes_request_and_stage_rows(monkeypatch):
    from src.schemas import RFIRequest

    stub = StubConnection()
    monkeypatch.setattr(api_main.psycopg, "connect", lambda *a, **kw: stub)
    response = CITED.model_copy(update={"usage": _usage_two_stages()})
    REAL_PERSIST_TRACE(RFIRequest(id="rfi-sql", question="  What   Primer? "),
                       response, "clarification", trace=None)

    (request_sql, request_params), = stub.executed
    assert "INSERT INTO rfi_requests" in request_sql
    _, question_sha, rfi_type, verdict, latency, cost = request_params
    assert (rfi_type, verdict, latency, cost) == ("clarification", "answered", 1500, 0.012)
    import hashlib
    assert question_sha == hashlib.sha256(b"what primer?").hexdigest()  # normalized + lowercased

    (stage_sql, rows), = stub.many
    assert "INSERT INTO rfi_request_stages" in stage_sql
    assert [(r[1], r[2], r[3], r[4], r[5], r[6]) for r in rows] == [
        ("classify", 500, 100, 10, 0.002, "claude-sonnet-5"),
        ("draft", 1000, 900, 80, 0.010, "claude-sonnet-5"),
    ]


def test_persist_trace_records_gap_verdict(monkeypatch):
    from src.schemas import RFIRequest

    stub = StubConnection()
    monkeypatch.setattr(api_main.psycopg, "connect", lambda *a, **kw: stub)
    response = GAP.model_copy(update={"usage": _usage_two_stages()})
    REAL_PERSIST_TRACE(RFIRequest(id="rfi-gv", question="q"), response, None, trace=None)
    (_, request_params), = stub.executed
    assert request_params[3] == "gap"
