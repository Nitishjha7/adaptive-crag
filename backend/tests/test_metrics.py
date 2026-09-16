"""Prometheus metrics — mirror what eval/RESULTS.md already measures.

No real LLM calls: `record_query` is exercised directly against fake
`CRAGState`/`token_usage` dicts, the same shapes `conftest.fake_llm` and
`graph.invoke` already produce in the routing tests.
"""

from prometheus_client import REGISTRY

from app.metrics import (
    COST_USD_TOTAL,
    GROUNDEDNESS_TOTAL,
    LLM_CALLS_TOTAL,
    LLM_FALLBACK_TRIGGERED_TOTAL,
    QUERIES_TOTAL,
    TOKENS_TOTAL,
    record_query,
)


def _counter_value(counter, **labels) -> float:
    return REGISTRY.get_sample_value(counter._name + "_total", labels) or 0.0


def test_record_query_increments_route_counter():
    before = _counter_value(QUERIES_TOTAL, route="vector_db")

    record_query({"source_type": "vector_db"}, {"by_model": {}}, elapsed_ms=500)

    assert _counter_value(QUERIES_TOTAL, route="vector_db") == before + 1


def test_record_query_records_groundedness_pass_and_fail():
    before_pass = _counter_value(GROUNDEDNESS_TOTAL, passed="true")
    before_fail = _counter_value(GROUNDEDNESS_TOTAL, passed="false")

    record_query(
        {"source_type": "vector_db", "guardrail_passed": True}, {"by_model": {}}, 100
    )
    record_query(
        {"source_type": "web_search", "guardrail_passed": False}, {"by_model": {}}, 100
    )

    assert _counter_value(GROUNDEDNESS_TOTAL, passed="true") == before_pass + 1
    assert _counter_value(GROUNDEDNESS_TOTAL, passed="false") == before_fail + 1


def test_record_query_tracks_calls_tokens_and_cost_by_model():
    model = "openai/gpt-oss-120b"
    before_calls = _counter_value(LLM_CALLS_TOTAL, model=model)
    before_in = _counter_value(TOKENS_TOTAL, model=model, direction="input")
    before_cost = _counter_value(COST_USD_TOTAL, model=model)

    token_usage = {
        "by_model": {
            model: {"calls": 3, "input_tokens": 100, "output_tokens": 50, "cost_usd": 0.02}
        }
    }
    record_query({"source_type": "vector_db"}, token_usage, 100)

    assert _counter_value(LLM_CALLS_TOTAL, model=model) == before_calls + 3
    assert _counter_value(TOKENS_TOTAL, model=model, direction="input") == before_in + 100
    assert _counter_value(COST_USD_TOTAL, model=model) == before_cost + 0.02


def test_unpriced_model_does_not_increment_cost_counter():
    model = "some-unpriced-model"
    before = _counter_value(COST_USD_TOTAL, model=model)

    token_usage = {"by_model": {model: {"calls": 1, "input_tokens": 10, "output_tokens": 10, "cost_usd": None}}}
    record_query({"source_type": "vector_db"}, token_usage, 100)

    assert _counter_value(COST_USD_TOTAL, model=model) == before


def test_fallback_triggered_when_answering_model_is_not_the_primary():
    before = _counter_value(LLM_FALLBACK_TRIGGERED_TOTAL)

    token_usage = {"by_model": {"openai/gpt-oss-20b": {"calls": 1, "input_tokens": 1, "output_tokens": 1}}}
    record_query(
        {"source_type": "vector_db"}, token_usage, 100, primary_model="openai/gpt-oss-120b"
    )

    assert _counter_value(LLM_FALLBACK_TRIGGERED_TOTAL) == before + 1


def test_no_fallback_when_only_primary_answered():
    before = _counter_value(LLM_FALLBACK_TRIGGERED_TOTAL)

    token_usage = {"by_model": {"openai/gpt-oss-120b": {"calls": 3, "input_tokens": 1, "output_tokens": 1}}}
    record_query(
        {"source_type": "vector_db"}, token_usage, 100, primary_model="openai/gpt-oss-120b"
    )

    assert _counter_value(LLM_FALLBACK_TRIGGERED_TOTAL) == before
