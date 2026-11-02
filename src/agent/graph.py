"""Happy-path agent graph: classify -> retrieve -> draft (DESIGN.md §3).

Usage (ad-hoc, from the repo root):
    .venv/bin/python -m src.agent.graph "Which paint system applies to interior steel?"
"""

import sys
import uuid
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from src.agent.nodes import classify, draft, retrieve
from src.agent.state import AgentState
from src.schemas import CitedResponse, RFIRequest

ROOT = Path(__file__).resolve().parent.parent.parent


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("classify", classify)
    graph.add_node("retrieve", retrieve)
    graph.add_node("draft", draft)
    graph.add_edge(START, "classify")
    graph.add_edge("classify", "retrieve")
    graph.add_edge("retrieve", "draft")
    graph.add_edge("draft", END)
    return graph.compile()


def run_rfi(question: str, rfi_id: str | None = None) -> CitedResponse:
    rfi = RFIRequest(id=rfi_id or f"rfi-{uuid.uuid4().hex[:8]}", question=question)
    final_state = build_graph().invoke({"rfi": rfi})
    return final_state["response"]


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
