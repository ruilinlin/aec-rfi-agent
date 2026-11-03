"""Tests for per-request telemetry collection (no network, no DB)."""

from src.agent.trace import PRICES_PER_MTOK, record_usage, stage, trace_run


def test_stage_records_latency_and_order():
    with trace_run() as trace:
        with stage("classify"):
            pass
        with stage("retrieve"):
            pass
    assert [s.stage for s in trace.stages] == ["classify", "retrieve"]
    assert all(s.latency_ms >= 0 for s in trace.stages)


def test_record_usage_attributes_tokens_and_cost_to_current_stage():
    with trace_run() as trace, stage("draft"):
        record_usage("claude-sonnet-5", 1_000_000, 100_000)
    draft = trace.stages[0]
    assert draft.input_tokens == 1_000_000
    assert draft.output_tokens == 100_000
    price_in, price_out = PRICES_PER_MTOK["claude-sonnet-5"]
    assert draft.cost_usd == price_in + 0.1 * price_out  # 1M in + 100K out
    assert draft.model == "claude-sonnet-5"


def test_unknown_model_records_tokens_but_zero_cost():
    with trace_run() as trace, stage("draft"):
        record_usage("some-future-model", 500, 500)
    assert trace.stages[0].cost_usd == 0.0
    assert trace.stages[0].model == "some-future-model"


def test_hooks_are_noops_without_active_trace():
    # Neither stage() nor record_usage() may raise or record outside trace_run.
    with stage("classify"):
        record_usage("claude-sonnet-5", 10, 10)


def test_usage_outside_any_stage_is_dropped():
    with trace_run() as trace:
        record_usage("claude-sonnet-5", 10, 10)  # no current stage
    assert trace.stages == []


def test_summary_totals_across_stages():
    with trace_run() as trace:
        with stage("retrieve"):
            record_usage("voyage-3.5", 1_000_000, 0)
        with stage("draft"):
            record_usage("claude-sonnet-5", 0, 1_000_000)
    summary = trace.summary()
    assert summary.total_cost_usd == 0.06 + 10.00
    assert [s.stage for s in summary.stages] == ["retrieve", "draft"]
    assert summary.total_latency_ms == sum(s.latency_ms for s in summary.stages)


def test_mixed_model_stage_accumulates_cost_but_keeps_last_model():
    # Documented semantics: tokens/cost sum across models, model is last-writer.
    with trace_run() as trace, stage("retrieve"):
        record_usage("voyage-3.5", 1_000_000, 0)
        record_usage("claude-sonnet-5", 1_000_000, 0)
    retrieve = trace.stages[0]
    assert retrieve.cost_usd == 0.06 + 2.00
    assert retrieve.input_tokens == 2_000_000
    assert retrieve.model == "claude-sonnet-5"
