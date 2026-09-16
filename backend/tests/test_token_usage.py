"""Per-query token/cost accounting — the precise replacement for the "3 calls
vs 4 calls" proxy in eval/RESULTS.md.

No real LLM calls: `_TrackingCallback.on_llm_end` is exercised directly with a
fake `LLMResult`-shaped object, the same way `conftest.fake_llm` scripts node
replies without a real model.
"""

from types import SimpleNamespace

from app.token_usage import UsageTracker, _current, new_tracker, TRACKING_CALLBACK


def _fake_response(model: str, prompt_tokens: int, completion_tokens: int):
    return SimpleNamespace(
        llm_output={
            "model_name": model,
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
        }
    )


def test_tracker_accumulates_across_multiple_calls_same_model():
    tracker = UsageTracker()
    tracker.record("openai/gpt-oss-120b", 100, 20)
    tracker.record("openai/gpt-oss-120b", 50, 10)

    summary = tracker.summary()
    usage = summary["by_model"]["openai/gpt-oss-120b"]
    assert usage["calls"] == 2
    assert usage["input_tokens"] == 150
    assert usage["output_tokens"] == 30
    assert usage["total_tokens"] == 180
    assert summary["total_calls"] == 2
    assert summary["total_tokens"] == 180


def test_summary_computes_cost_for_priced_model():
    tracker = UsageTracker()
    tracker.record("openai/gpt-oss-120b", 1_000_000, 1_000_000)

    summary = tracker.summary()
    # $0.15 in + $0.75 out per million tokens
    assert summary["by_model"]["openai/gpt-oss-120b"]["cost_usd"] == 0.90
    assert summary["total_cost_usd"] == 0.90


def test_unpriced_model_has_none_cost_not_zero():
    """An unpriced model costing '$0.00' is a different, false claim from 'we
    don't know the price' — the total must reflect that it is a lower bound."""
    tracker = UsageTracker()
    tracker.record("some-new-model", 1000, 1000)

    summary = tracker.summary()
    assert summary["by_model"]["some-new-model"]["cost_usd"] is None
    assert summary["total_cost_usd"] is None


def test_mixed_priced_and_unpriced_models_total_is_none():
    tracker = UsageTracker()
    tracker.record("openai/gpt-oss-120b", 1_000_000, 0)
    tracker.record("unknown-model", 1000, 1000)

    summary = tracker.summary()
    assert summary["by_model"]["openai/gpt-oss-120b"]["cost_usd"] == 0.15
    assert summary["total_cost_usd"] is None


def test_callback_records_into_whichever_tracker_is_current():
    tracker = new_tracker()
    TRACKING_CALLBACK.on_llm_end(_fake_response("openai/gpt-oss-120b", 40, 8))

    assert tracker.summary()["total_tokens"] == 48
    _current.set(None)


def test_callback_is_a_noop_with_no_current_tracker():
    """Between requests (or if a caller forgets to open one), the callback
    must not raise — see main.py, which always opens one, but a stray call
    from a background task or a test must fail safe."""
    _current.set(None)
    # Must not raise.
    TRACKING_CALLBACK.on_llm_end(_fake_response("openai/gpt-oss-120b", 10, 10))


def test_two_trackers_do_not_mix_tokens():
    """The whole reason for a contextvar instead of a module global — two
    'requests' (simulated here as two tracker lifetimes) must not see each
    other's usage."""
    tracker_a = new_tracker()
    TRACKING_CALLBACK.on_llm_end(_fake_response("openai/gpt-oss-120b", 10, 10))

    tracker_b = new_tracker()
    TRACKING_CALLBACK.on_llm_end(_fake_response("openai/gpt-oss-120b", 99, 99))

    assert tracker_a.summary()["total_tokens"] == 20
    assert tracker_b.summary()["total_tokens"] == 198
    _current.set(None)
