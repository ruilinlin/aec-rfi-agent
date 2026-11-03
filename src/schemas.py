"""Pydantic schemas for the agent's inputs and outputs (DESIGN.md §5)."""

from pydantic import BaseModel


class RFIRequest(BaseModel):
    id: str
    question: str
    references: list[str] = []


class Citation(BaseModel):
    chunk_id: str
    section_code: str | None
    sheet: str | None = None
    revision: str
    quote_span: str


class UsageStage(BaseModel):
    stage: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: str | None = None


class UsageSummary(BaseModel):
    total_latency_ms: int
    total_cost_usd: float
    stages: list[UsageStage]


class CitedResponse(BaseModel):
    rfi_id: str
    rfi_type: str
    answer: str
    citations: list[Citation]
    superseded_notes: list[str] = []
    usage: UsageSummary | None = None


class GapReport(BaseModel):
    rfi_id: str
    reason: str
    searched: list[str]
    closest_matches: list[Citation] = []
    usage: UsageSummary | None = None
