"""FastAPI service exposing the agent: POST /rfi -> CitedResponse | GapReport.

Usage (from the repo root):
    .venv/bin/uvicorn src.api.main:app --reload
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI

from src.agent.graph import build_graph
from src.schemas import CitedResponse, GapReport, RFIRequest

ROOT = Path(__file__).resolve().parent.parent.parent

load_dotenv(ROOT / ".env")

app = FastAPI(
    title="aec-rfi-agent",
    description="Drafts cited answers to construction RFIs; reports gaps instead of guessing.",
)


@lru_cache(maxsize=1)
def get_graph():
    """Compile the agent graph once per process; overridable in tests."""
    return build_graph()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/rfi", response_model=CitedResponse | GapReport)
def answer_rfi(
    rfi: RFIRequest, graph: Annotated[object, Depends(get_graph)]
) -> CitedResponse | GapReport:
    """Run the full agent on one RFI.

    The response is a CitedResponse when governing evidence supports an
    answer, and a GapReport when it does not. The drafted answer is for a
    licensed professional to review; the agent never issues final answers.
    """
    final_state = graph.invoke({"rfi": rfi})
    return final_state["response"]
