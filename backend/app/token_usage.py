"""Per-query token and cost accounting.

`eval/RESULTS.md` already makes the cost argument for adaptive routing —
"local 3 calls, web 4 calls" — after finding that latency could not be
measured cleanly (Groq throttling made an early latency comparison
meaningless; see the "cost argument" section of that file). A call count is a
real number, but it treats every LLM call as equally expensive, which they are
not: `grade_documents` reads a handful of chunks, `generate` reads the same
chunks plus writes a whole answer. Real token and dollar accounting is the
natural upgrade — same claim, sharper number.

`get_llm()` is `@lru_cache`'d, so the four call sites (`grade_documents`,
`transform_query`, `generate`, `validate_guardrails`) share one or two actual
`ChatGroq` instances, not one each. That is why this is a `contextvars.ContextVar`
rather than a plain module-level counter: a counter on the shared client would
mix tokens from concurrent requests together, and the question this exists to
answer is "what did *this* query cost", not "what has this process cost since
it booted". `main.py` opens one tracker per request; the callback bound onto
every client (once, in `get_llm`) always records into whichever tracker is
current, so two concurrent requests never see each other's tokens.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, field

from langchain_core.callbacks.base import BaseCallbackHandler

# Per-million-token prices, USD, current as of the models this project uses.
# Deliberately small and inline rather than a pricing library dependency for
# two numbers Groq publishes. Update alongside LLM_MODEL / LLM_FALLBACK_MODELS
# if the configured models change — an unlisted model prices at $0 in the
# by-model breakdown but is excluded from the total (see `summary` below),
# rather than silently under-costing it as free.
_PRICE_PER_MILLION_USD = {
    "openai/gpt-oss-120b": {"input": 0.15, "output": 0.75},
    "openai/gpt-oss-20b": {"input": 0.10, "output": 0.50},
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
}


@dataclass
class ModelUsage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class UsageTracker:
    """Accumulates token usage across every LLM call in one query."""

    by_model: dict[str, ModelUsage] = field(default_factory=dict)

    def record(self, model: str, input_tokens: int, output_tokens: int) -> None:
        usage = self.by_model.setdefault(model, ModelUsage())
        usage.calls += 1
        usage.input_tokens += input_tokens
        usage.output_tokens += output_tokens

    def summary(self) -> dict:
        """The shape returned to the API — see `QueryOut.token_usage` in main.py."""
        by_model: dict[str, dict] = {}
        total_tokens = 0
        total_calls = 0
        total_cost = 0.0
        priced_every_model = True

        for model, usage in self.by_model.items():
            price = _PRICE_PER_MILLION_USD.get(model)
            cost = None
            if price is not None:
                cost = (
                    usage.input_tokens * price["input"]
                    + usage.output_tokens * price["output"]
                ) / 1_000_000
                total_cost += cost
            else:
                priced_every_model = False
            by_model[model] = {
                "calls": usage.calls,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
                # None, not 0.0 — an unpriced model costing "nothing" is a
                # different claim than "we don't know the price".
                "cost_usd": cost,
            }
            total_tokens += usage.total_tokens
            total_calls += usage.calls

        return {
            "by_model": by_model,
            "total_calls": total_calls,
            "total_tokens": total_tokens,
            # If any model that ran isn't in the price table, the total is a
            # lower bound, not a real total — say so rather than under-report.
            "total_cost_usd": total_cost if priced_every_model else None,
        }


_current: contextvars.ContextVar[UsageTracker | None] = contextvars.ContextVar(
    "crag_usage_tracker", default=None
)


class _TrackingCallback(BaseCallbackHandler):
    """Bound once onto every LLM client `get_llm()` builds. Stateless by
    itself — reads whatever tracker is current for this call, via the
    contextvar above, so the same callback instance is safe to share across
    every cached client (primary and fallback) and every concurrent request."""

    def on_llm_end(self, response, **kwargs) -> None:  # noqa: D102
        tracker = _current.get()
        if tracker is None:
            return
        llm_output = response.llm_output or {}
        model = llm_output.get("model_name", "unknown")
        usage = llm_output.get("token_usage") or {}
        tracker.record(
            model=model,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )


# The one callback instance every `get_llm()` client is bound to.
TRACKING_CALLBACK = _TrackingCallback()


def new_tracker() -> UsageTracker:
    """Start tracking for one query. Call this before invoking the graph, then
    read `.summary()` after — see `app.graph.build_graph` / `main.py`."""
    tracker = UsageTracker()
    _current.set(tracker)
    return tracker
