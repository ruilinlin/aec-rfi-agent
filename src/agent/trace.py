"""Per-request pipeline telemetry: stage latency, token usage, and cost.

A Trace is activated with trace_run() around one agent invocation; each graph
node runs inside stage(), and the LLM/embedding clients report their usage
into whichever stage is current. Outside an active trace every hook is a
no-op, so eval runs and ingest pay zero overhead unless they opt in.

The StageRecord shape is deliberately the prototype for the future SSE trace
event schema: one event per stage with latency, tokens, cost, and model.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from src.schemas import UsageStage, UsageSummary

# USD per million tokens (input, output). Unknown models record zero cost
# rather than guessing; the model name is still stored for later repricing.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-sonnet-5": (2.00, 10.00),
    "voyage-3.5": (0.06, 0.0),
}


@dataclass
class StageRecord:
    stage: str
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    model: str | None = None


@dataclass
class Trace:
    stages: list[StageRecord] = field(default_factory=list)

    def summary(self) -> UsageSummary:
        # Round per stage FIRST and total the rounded values, so the persisted
        # total always equals SUM(stage rows) in SQL reconciliation queries.
        stage_models = [
            UsageStage(
                stage=record.stage,
                latency_ms=record.latency_ms,
                input_tokens=record.input_tokens,
                output_tokens=record.output_tokens,
                cost_usd=round(record.cost_usd, 6),
                model=record.model,
            )
            for record in self.stages
        ]
        return UsageSummary(
            total_latency_ms=sum(stage.latency_ms for stage in stage_models),
            total_cost_usd=round(sum(stage.cost_usd for stage in stage_models), 6),
            stages=stage_models,
        )


_current_trace: ContextVar[Trace | None] = ContextVar("current_trace", default=None)
# The current stage is its own ContextVar (not an attribute on the shared
# Trace) so that if the graph ever runs stages concurrently, each task's
# copied context attributes usage to its own stage record.
_current_stage: ContextVar[StageRecord | None] = ContextVar("current_stage", default=None)


@contextmanager
def trace_run():
    """Activate a fresh Trace for the duration of one agent invocation."""
    trace = Trace()
    token = _current_trace.set(trace)
    try:
        yield trace
    finally:
        _current_trace.reset(token)


@contextmanager
def stage(name: str):
    """Time one pipeline stage; usage reported inside lands on this record."""
    trace = _current_trace.get()
    if trace is None:
        yield
        return
    record = StageRecord(stage=name)
    trace.stages.append(record)
    token = _current_stage.set(record)
    started = time.perf_counter()
    try:
        yield
    finally:
        record.latency_ms = int((time.perf_counter() - started) * 1000)
        _current_stage.reset(token)


def record_usage(model: str, input_tokens: int, output_tokens: int) -> None:
    """Attribute token usage (and derived cost) to the current stage, if any.

    Semantics for several calls within one stage: tokens and cost accumulate
    across all calls (and models), while `model` is last-writer-wins - a stage
    mixing embedding and LLM calls keeps the LLM's name but the combined cost.
    """
    trace = _current_trace.get()
    record = _current_stage.get()
    if trace is None or record is None:
        return
    record.model = model
    record.input_tokens += input_tokens
    record.output_tokens += output_tokens
    price_in, price_out = PRICES_PER_MTOK.get(model, (0.0, 0.0))
    record.cost_usd += (input_tokens * price_in + output_tokens * price_out) / 1_000_000
