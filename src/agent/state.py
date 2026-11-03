"""The state object passed between agent graph nodes."""

from typing import TypedDict

from src.schemas import Citation, CitedResponse, GapReport, RFIRequest


class AgentState(TypedDict, total=False):
    rfi: RFIRequest
    retrieval_table: str
    rfi_type: str
    references: list[str]
    chunks: list[dict]
    query_embedding: list[float]
    superseded_notes: list[str]
    draft_answer: str
    draft_citations: list[Citation]
    response: CitedResponse | GapReport
