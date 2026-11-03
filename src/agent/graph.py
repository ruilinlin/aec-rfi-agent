"""Agent graph: classify -> retrieve -> cross_check -> draft -> verify (DESIGN.md §3).

Usage (ad-hoc, from the repo root):
    .venv/bin/python -m src.agent.graph "Which paint system applies to interior steel?"
"""

import sys
import uuid
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from src.agent.nodes import classify, cross_check, draft, finalize_unverified, retrieve, verify
from src.agent.state import AgentState
from src.agent.trace import stage, trace_run
from src.schemas import CitedResponse, GapReport, RFIRequest

ROOT = Path(__file__).resolve().parent.parent.parent


def _traced(name: str, node):
    """Run a node inside a telemetry stage (no-op without an active trace)."""

    def wrapped(state):
        with stage(name):
            return node(state)

    return wrapped


def build_graph(*, with_cross_check: bool = True, with_verify: bool = True):
    """Compile the agent graph; flags drop one stage each for the ablations."""
    graph = StateGraph(AgentState)
    graph.add_node("classify", _traced("classify", classify))
    graph.add_node("retrieve", _traced("retrieve", retrieve))
    graph.add_node("draft", _traced("draft", draft))
    graph.add_edge(START, "classify")
    graph.add_edge("classify", "retrieve")
    if with_cross_check:
        graph.add_node("cross_check", _traced("cross_check", cross_check))
        graph.add_edge("retrieve", "cross_check")
        graph.add_edge("cross_check", "draft")
    else:
        graph.add_edge("retrieve", "draft")
    if with_verify:
        graph.add_node("verify", _traced("verify", verify))
        graph.add_edge("draft", "verify")
        graph.add_edge("verify", END)
    else:
        graph.add_node("finalize", _traced("finalize", finalize_unverified))
        graph.add_edge("draft", "finalize")
        graph.add_edge("finalize", END)
    return graph.compile()


def run_rfi(question: str, rfi_id: str | None = None) -> CitedResponse | GapReport:
    rfi = RFIRequest(id=rfi_id or f"rfi-{uuid.uuid4().hex[:8]}", question=question)
    with trace_run() as trace:
        final_state = build_graph().invoke({"rfi": rfi})
    # model_copy instead of in-place mutation: a graph that ever returns a
    # shared/cached response object must not leak one request's usage into
    # another's.
    return final_state["response"].model_copy(update={"usage": trace.summary()})


def main() -> int:
    from dotenv import load_dotenv

    if len(sys.argv) < 2:
        print('usage: python -m src.agent.graph "your RFI question"')
        return 2
    load_dotenv(ROOT / ".env")
    response = run_rfi(sys.argv[1])
    print(response.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
