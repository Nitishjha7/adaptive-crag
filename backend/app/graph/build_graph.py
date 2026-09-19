r"""LangGraph StateGraph wiring.

    START -> retrieve -> grade_documents -> [conditional]
                                             |-- "yes" --> generate
                                             \-- "no"  --> transform_query
                                                            -> web_search_fallback
                                                            -> generate
             generate -> validate_guardrails -> END

**Why a graph and not a chain:** the node that runs after `grade_documents` is
not fixed at compile time — it is chosen at runtime by reading state. A linear
chain cannot express that.
"""

import time

from langgraph.graph import END, START, StateGraph

from app.nodes import (
    generate,
    grade_documents,
    retrieve,
    transform_query,
    validate_guardrails,
    web_search_fallback,
)
from app.schemas.crag_state import CRAGState, initial_state


def decide_to_generate(state: CRAGState) -> str:
    """Routing function — the conditional edge dispatches on its return value.

    Deliberately trivial: the decision is made in `grade_documents`, and this
    only reads the result. Keeping routing and grading apart lets each be tested
    on its own — the router's tests need no LLM at all.

    Note what the default is. Only an exact "yes" generates; everything else —
    "no", an empty string, a missing key — takes the correction path. If
    `relevance_score` is ever empty because of a bug, the safe direction is to
    go and check rather than to answer from unverified context.
    """
    return "generate" if state.get("relevance_score") == "yes" else "transform_query"


def build_crag_graph():
    """Returns the compiled graph. Called once at module load."""
    g = StateGraph(CRAGState)

    g.add_node("retrieve", retrieve.run)
    g.add_node("grade_documents", grade_documents.run)
    g.add_node("transform_query", transform_query.run)
    g.add_node("web_search_fallback", web_search_fallback.run)
    g.add_node("generate", generate.run)
    g.add_node("validate_guardrails", validate_guardrails.run)

    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "grade_documents")

    g.add_conditional_edges(
        "grade_documents",
        decide_to_generate,
        {"generate": "generate", "transform_query": "transform_query"},
    )

    # The correction path
    g.add_edge("transform_query", "web_search_fallback")
    g.add_edge("web_search_fallback", "generate")

    # Both branches merge here. Not two generate nodes: `generate` only reads
    # state["documents"] and should not know where the context came from.
    g.add_edge("generate", "validate_guardrails")
    g.add_edge("validate_guardrails", END)

    return g.compile()


# --------------------------------------------------------------------------- #
# Streaming
# --------------------------------------------------------------------------- #

# What each node update is worth telling a live caller, built from the state
# it just wrote rather than a static label — this project's real story is the
# corrective routing decision, so the progress event should say *what was
# decided*, not just which node ran.
def _describe_update(node_name: str, partial: dict) -> str:
    if node_name == "retrieve":
        n = len(partial.get("documents") or [])
        return f"retrieve: got {n} chunk(s) from the local index"
    if node_name == "grade_documents":
        score = partial.get("relevance_score", "?")
        verdict = "relevant, answering locally" if score == "yes" else "not relevant, falling back to web"
        return f"grade_documents: relevance={score} ({verdict})"
    if node_name == "transform_query":
        return f"transform_query: rewrote query to {partial.get('transformed_query', '')!r}"
    if node_name == "web_search_fallback":
        n = len(partial.get("documents") or [])
        return f"web_search_fallback: got {n} web snippet(s)"
    if node_name == "generate":
        return "generate: answer drafted from context"
    if node_name == "validate_guardrails":
        passed = partial.get("guardrail_passed")
        return f"validate_guardrails: {'passed' if passed else 'flagged'}"
    return node_name


def run_query_stream(question: str, graph=None, state: CRAGState | None = None):
    """Same query as `graph.invoke(initial_state(question))`, yielded one node
    at a time.

    `state` lets a caller (main.py's `/api/query/stream`) pass in an
    `initial_state()` already populated with `memory_note` - see
    `_state_with_memory` in main.py - rather than this function reaching into
    `app.memory` itself and coupling a graph-execution helper to a feature
    that lives one layer above it.

    A local hit finishes in 3 LLM calls; the correction path takes 4 plus a web
    round trip — `graph.invoke` makes both look identical to a caller until the
    whole thing is done. This generator yields a `("progress", {...})` tuple the
    moment each node finishes, so the corrective routing decision (the thing
    this project is actually about) becomes visible as it happens, then a final
    `("done", CRAGState)` with everything a non-streaming call would return.

    Built on `graph.stream(..., stream_mode="updates")` rather than a second,
    hand-written traversal — the node functions and edges in `build_crag_graph`
    are the single source of truth for both paths, so this cannot drift from
    what a plain `.invoke()` actually executes.

    `graph` defaults to a fresh `build_crag_graph()` call (cheap — it is just
    wiring nodes together) so tests and one-off callers don't need one, but
    `main.py` passes the module-level compiled instance to avoid rebuilding it
    per request, matching `/api/query`.
    """
    started = time.perf_counter()
    state = state if state is not None else initial_state(question)
    graph = graph or build_crag_graph()

    for update in graph.stream(state, stream_mode="updates"):
        # `update` is `{node_name: partial_state}` — exactly one node per
        # dict on this graph (no parallel branches), but iterate rather than
        # assume, in case the topology ever grows one.
        for node_name, partial in update.items():
            # Plain `dict.update` would silently break `logs`: its reducer is
            # `operator.add` (schemas/crag_state.py), so LangGraph's own
            # internal state appends each node's line, but a partial update
            # here only ever carries *that node's* single new line, not the
            # accumulated list. Overwriting with `state.update(partial)`
            # would leave `state["logs"]` holding only the last node's line
            # by the time this generator finishes — the bug caught by
            # `test_stream_endpoint_matches_non_streaming_payload_shape`.
            label = _describe_update(node_name, partial)
            # Pop before merging: `state.update` below would otherwise
            # overwrite the accumulated `logs` list with just this node's
            # one new line, since `partial["logs"]` only ever carries the
            # single line that node's own `run()` returned.
            new_logs = partial.pop("logs", None)

            state.update(partial)
            if new_logs is not None:
                state["logs"] = state.get("logs", []) + list(new_logs)

            yield "progress", {
                "node": node_name,
                "label": label,
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
            }

    yield "done", state
