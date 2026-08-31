"""LangGraph StateGraph wiring.

Phase 2 (abhi) — sirf linear skeleton:

    START -> retrieve -> generate -> END

Phase 3 me `grade_documents` + conditional edge + `transform_query` +
`web_search_fallback` add honge, Phase 4 me `validate_guardrails`. Target shape
TECHNICAL_SPEC.md section 3 me hai.

**Chain kyun nahi, graph kyun** — abhi to ye linear hi lag raha hai. Fayda Phase 3
me dikhta hai: path runtime pe grader ke output se decide hoga. Chain linear hi
reh sakti hai; StateGraph me conditional edge daalne ke liye code dobara nahi
likhna padta, bas ek edge badalti hai.
"""

from langgraph.graph import END, START, StateGraph

from app.nodes import generate, retrieve
from app.schemas.crag_state import CRAGState


def build_crag_graph():
    """Compiled graph return karta hai. Module load pe ek baar call hota hai."""
    g = StateGraph(CRAGState)

    g.add_node("retrieve", retrieve.run)
    g.add_node("generate", generate.run)

    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", END)

    # TODO(Phase 3): grade_documents node + conditional edge:
    #   retrieve -> grade_documents -> {yes: generate, no: transform_query}
    #   transform_query -> web_search_fallback -> generate
    # TODO(Phase 4): generate -> validate_guardrails -> END

    return g.compile()
