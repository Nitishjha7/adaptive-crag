"""CRAGState — the graph's single source of truth.

Nodes return a partial dict holding only the keys they changed, and LangGraph
merges those updates in.

How a merge behaves is decided per key by its **reducer**:

- `logs` has an additive reducer — every node appends one line, and no node has
  to know what ran before it. A full execution trace falls out for free, and it
  is what the UI renders under each answer.

- `documents` **overwrites** (the default, no reducer) — and this is deliberate.
  `retrieve` sets the local chunks; on the fallback path `web_search_fallback`
  **replaces** them rather than appending. The local documents have just been
  graded "no"; keeping them in context would dilute the good context and bring
  back the hallucination risk the grading step exists to remove.

  That makes this the highest-leverage line in the file: adding `operator.add`
  here would reintroduce the bug without changing a single node.
"""

import operator
from typing import Annotated, List

from typing_extensions import TypedDict


class CRAGState(TypedDict, total=False):
    # --- input -------------------------------------------------------------
    question: str
    """The original user query. Never mutated — the rewrite goes in its own key,
    so the trace can show what the user asked and what the system turned it into."""

    # --- set by transform_query --------------------------------------------
    transformed_query: str
    """Keyword-focused web search query. Only filled on the fallback path."""

    # --- working context ---------------------------------------------------
    documents: List[str]
    """Working context. Set by `retrieve`, replaced by `web_search_fallback`."""

    # --- set by grade_documents --------------------------------------------
    relevance_score: str
    """"yes" | "no" — what the conditional edge routes on."""

    source_type: str
    """"vector_db" | "web_search" — drives the source badge in the UI."""

    sources: List[str]
    """Citations — filenames on the local path, URLs on the web path.

    Travels alongside `documents` rather than inside it, so `documents` stays a
    plain `List[str]` and `generate`'s contract holds: it reads context and does
    not need to know where that context came from.

    Overwrites for the same reason `documents` does — otherwise the UI would
    cite local filenames under a web-sourced answer."""

    # --- output ------------------------------------------------------------
    generation: str
    """The raw LLM answer, not yet guardrail-checked."""

    final_output: str
    """The guardrail-validated answer — this is what reaches the user."""

    guardrail_passed: bool
    """Whether the guardrails came back clean (groundedness and PII together).

    Also written into `logs`, but parsing it back out of a log line is string
    matching. The eval harness needs a structured field that does not break when
    the wording of a log changes."""

    # --- trace -------------------------------------------------------------
    logs: Annotated[List[str], operator.add]
    """Node-by-node execution trace. Additive — each node appends one line."""


def initial_state(question: str) -> CRAGState:
    """Builds a fresh state for one query.

    Initialising in one place matters: the additive reducer on `logs` operates on
    a list and would crash on `None`, so it has to start as `[]`.

    Every request builds a new one. There is no checkpointer and no memory — the
    graph is stateless, which is why the UI's history is labelled a record rather
    than conversation memory.
    """
    return {
        "question": question,
        "transformed_query": "",
        "documents": [],
        "sources": [],
        "relevance_score": "",
        "source_type": "vector_db",
        "generation": "",
        "final_output": "",
        "logs": [],
    }
