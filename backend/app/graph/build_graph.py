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

from langgraph.graph import END, START, StateGraph

from app.nodes import (
    generate,
    grade_documents,
    retrieve,
    transform_query,
    validate_guardrails,
    web_search_fallback,
)
from app.schemas.crag_state import CRAGState


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
