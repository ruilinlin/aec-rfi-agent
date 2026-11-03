"""Tests for the gap loop: clustering math, closure notes, persistence SQL.
No LLM, no real DB."""

import importlib.util
from pathlib import Path

from src.schemas import Citation, CitedResponse, GapReport

_spec = importlib.util.spec_from_file_location(
    "gap_loop", Path(__file__).resolve().parent.parent / "scripts" / "gap_loop.py"
)
gl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gl)


def _gap(qid, embedding, searched=None):
    return {"id": qid, "question": qid, "searched": searched or [], "embedding": embedding}


def test_cluster_groups_similar_questions_and_separates_distant_ones():
    a1 = _gap("elevator-1", [1.0, 0.0, 0.0])
    a2 = _gap("elevator-2", [0.95, 0.05, 0.0])  # near a1
    b = _gap("fire-alarm", [0.0, 1.0, 0.0])  # orthogonal
    clusters = gl.cluster_gaps([a1, a2, b], threshold=0.8)
    assert [len(c) for c in clusters] == [2, 1]
    assert {g["id"] for g in clusters[0]} == {"elevator-1", "elevator-2"}


def test_cluster_is_deterministic_and_anchor_based():
    # The second member does NOT drag the anchor: c is close to b but not to a,
    # so it must not join a cluster anchored at a even after b joined it.
    a = _gap("a", [1.0, 0.0])
    b = _gap("b", [0.85, 0.53])  # cos(a,b) ~ 0.85 -> joins a's cluster
    c = _gap("c", [0.55, 0.84])  # cos(a,c) ~ 0.55, cos(b,c) ~ 0.91
    clusters = gl.cluster_gaps([a, b, c], threshold=0.8)
    assert [len(cl) for cl in clusters] == [2, 1]
    assert clusters[1][0]["id"] == "c"


def test_cosine_handles_zero_vectors():
    assert gl.cosine([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_closure_note_lists_cited_sections_and_manifest():
    response = CitedResponse(
        rfi_id="r",
        rfi_type="clarification",
        answer="a",
        citations=[
            Citation(chunk_id="x:1", section_code="14 20 00", revision="UFGS-2027-02", quote_span="q"),
            Citation(chunk_id="x:2", section_code="14 20 00", revision="UFGS-2027-02", quote_span="q2"),
        ],
    )
    note = gl.closure_note(response, "abc123def456")
    assert note == "answered citing 14 20 00@UFGS-2027-02; corpus manifest abc123def456"


def test_cluster_threshold_boundary_is_inclusive():
    a = _gap("a", [1.0, 0.0])
    b = _gap("b", [0.8, 0.6])  # cos(a,b) == 0.8 exactly
    assert len(gl.cluster_gaps([a, b], threshold=0.8)) == 1


def test_closure_note_falls_back_to_sheet_then_chunk_id():
    response = CitedResponse(
        rfi_id="r", rfi_type="clarification", answer="a",
        citations=[
            Citation(chunk_id="d:1", section_code=None, sheet="A-101",
                     revision="Addendum 2", quote_span="q"),
            Citation(chunk_id="d:2", section_code=None, sheet=None,
                     revision="Addendum 2", quote_span="q"),
        ],
    )
    note = gl.closure_note(response, "m")
    assert "A-101@Addendum 2" in note and "d:2@Addendum 2" in note
    assert "None@" not in note


class ReplayStubConn:
    def __init__(self, rows):
        self.rows = rows
        self.updates = []

    def execute(self, sql, params=None):
        if sql.strip().startswith("SELECT"):
            class R:
                def __init__(self, rows): self._rows = rows
                def fetchall(self): return self._rows
            return R(self.rows)
        self.updates.append(params)
        class R2:
            def fetchall(self): return []
        return R2()


class ScriptedGraph:
    """Returns scripted responses per question; can raise mid-run."""

    def __init__(self, script):
        self.script = script

    def invoke(self, state):
        outcome = self.script[state["rfi"].question]
        if isinstance(outcome, Exception):
            raise outcome
        return {"response": outcome}


def _cited(sections=("09 90 00",)):
    return CitedResponse(
        rfi_id="r", rfi_type="clarification", answer="a",
        citations=[
            Citation(chunk_id=f"c:{s}", section_code=s, revision="UFGS-2026-08", quote_span="q")
            for s in sections
        ],
    )


def test_replay_closes_cited_skips_gaps_and_survives_failures(monkeypatch, capsys):
    import src.agent.graph as graph_module

    script = {
        "q-closes": _cited(),
        "q-still-gap": GapReport(rfi_id="r", reason="no", searched=[]),
        "q-uncited": _cited(sections=()),  # answered without citations: no close
        "q-crashes": RuntimeError("llm down"),
        "q-closes-2": _cited(sections=("22 00 00",)),
    }
    monkeypatch.setattr(graph_module, "build_graph", lambda **kw: ScriptedGraph(script))
    monkeypatch.setattr(gl, "manifest_sha", lambda: "m0")
    conn = ReplayStubConn([(f"g{i}", q) for i, q in enumerate(script)])
    gl.cmd_replay(conn, limit=None)

    closed_ids = [params[1] for params in conn.updates]
    assert closed_ids == ["g0", "g4"]  # only the two cited answers close
    out = capsys.readouterr().out
    assert "FAILED: RuntimeError" in out  # the crash is reported, not fatal
    assert "closed 2, failed 1" in out
    assert "replay cost" in out  # cost line always printed


def test_fetch_open_gaps_parses_pgvector_text():
    conn = ReplayStubConn([("g1", "question one", ["09 90 00"], "[0.1,0.9]")])
    gaps = gl.fetch_open_gaps(conn)
    assert gaps[0]["embedding"] == [0.1, 0.9]
