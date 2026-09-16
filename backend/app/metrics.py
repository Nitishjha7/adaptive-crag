"""Prometheus metrics for what this project already measures elsewhere.

These mirror `eval/RESULTS.md`, not generic request counters bolted on
afterwards:

- **Routing** (`vector_db` vs `web_search`) is the eval's headline number.
- **Groundedness pass/fail** comes straight out of `validate_guardrails`.

**What is deliberately not here:** `eval/RESULTS.md`'s missed-fallback /
unnecessary-fallback taxonomy needs a ground-truth label for whether a
question actually required `web` — that label only exists in
`eval/scenarios.json`, written by hand against the corpus. A live production
request carries no such label, so a live "missed fallback" counter would have
to guess at the very thing the eval exists to check, and a guessed metric
with a real-sounding name is worse than no metric. That distinction stays an
eval-only measurement; `crag_groundedness_total` is the live signal that
correlates with it (an answer built on a missed fallback is exactly the case
`validate_guardrails` is most likely to catch as ungrounded).
- **Tokens and cost** are the precise replacement for the "3 calls vs 4 calls"
  proxy — see app/token_usage.py.
- **LLM calls** by model, and whether a fallback model answered instead of the
  configured primary — the gateway's own health signal.

`prometheus_client` rather than a hand-rolled exposition format: the text
format has escaping and type-comment rules a real Prometheus server is
unforgiving about, and this is what every production FastAPI service uses.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

# --------------------------------------------------------------------------- #
# Routing — the eval's headline metric, live
# --------------------------------------------------------------------------- #

QUERIES_TOTAL = Counter(
    "crag_queries_total",
    "Queries answered, by route taken.",
    ["route"],  # "vector_db" | "web_search"
)

QUERY_DURATION_SECONDS = Histogram(
    "crag_query_duration_seconds",
    "Wall-clock time for one query, end to end.",
    ["route"],
    # RESULTS.md found Groq throttling swamps the local/web latency gap at
    # this scale — buckets are wide enough to still be useful as an operational
    # signal without implying the gap they could not establish is real.
    buckets=(0.5, 1, 2, 5, 10, 20, 40),
)

# --------------------------------------------------------------------------- #
# The correction path's own error taxonomy (eval/RESULTS.md)
# --------------------------------------------------------------------------- #

GROUNDEDNESS_TOTAL = Counter(
    "crag_groundedness_total",
    "validate_guardrails groundedness verdicts.",
    ["passed"],  # "true" | "false"
)

# --------------------------------------------------------------------------- #
# The LLM gateway
# --------------------------------------------------------------------------- #

LLM_CALLS_TOTAL = Counter(
    "crag_llm_calls_total",
    "LLM calls that returned a response, by model.",
    ["model"],
)

LLM_FALLBACK_TRIGGERED_TOTAL = Counter(
    "crag_llm_fallback_triggered_total",
    "Times the primary model failed and a fallback model answered instead.",
)

TOKENS_TOTAL = Counter(
    "crag_llm_tokens_total",
    "Tokens consumed, by model and direction.",
    ["model", "direction"],  # direction: "input" | "output"
)

COST_USD_TOTAL = Counter(
    "crag_llm_cost_usd_total",
    "Estimated USD cost of LLM calls, by model. Only incremented for models "
    "with a known price — see app/token_usage.py's price table.",
    ["model"],
)


def record_query(state: dict, token_usage: dict, elapsed_ms: int, primary_model: str | None = None) -> None:
    """Update every query-level metric from one finished `CRAGState`.

    One function, called once per query in `main.py` (both `/api/query` and
    the streaming endpoint's final event), rather than scattering `.inc()`
    calls through the graph nodes — the nodes stay exactly what they were
    before metrics existed.
    """
    route = state.get("source_type") or "unknown"
    QUERIES_TOTAL.labels(route=route).inc()
    QUERY_DURATION_SECONDS.labels(route=route).observe(elapsed_ms / 1000)

    if "guardrail_passed" in state:
        GROUNDEDNESS_TOTAL.labels(passed=str(bool(state["guardrail_passed"])).lower()).inc()

    by_model = token_usage.get("by_model") or {}
    models_that_answered = list(by_model.keys())
    for model, stats in by_model.items():
        LLM_CALLS_TOTAL.labels(model=model).inc(stats.get("calls", 0))
        TOKENS_TOTAL.labels(model=model, direction="input").inc(stats.get("input_tokens", 0))
        TOKENS_TOTAL.labels(model=model, direction="output").inc(stats.get("output_tokens", 0))
        if stats.get("cost_usd") is not None:
            COST_USD_TOTAL.labels(model=model).inc(stats["cost_usd"])

    # A fallback fired if more than one model answered during this query
    # (primary failed partway through), or if the only model that answered
    # isn't the configured primary at all (primary failed on every call).
    fell_back = len(models_that_answered) > 1 or (
        primary_model is not None
        and len(models_that_answered) == 1
        and models_that_answered[0] != primary_model
    )
    if fell_back:
        LLM_FALLBACK_TRIGGERED_TOTAL.inc()
