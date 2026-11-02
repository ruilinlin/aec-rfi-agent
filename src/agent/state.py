"""The state object passed between agent graph nodes."""

from typing import TypedDict

from src.schemas import CitedResponse, RFIRequest


class AgentState(TypedDict, total=False):
    rfi: RFIRequest
    rfi_type: str
    references: list[str]
    chunks: list[dict]
    response: CitedResponse
