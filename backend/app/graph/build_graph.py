"""LangGraph StateGraph wiring.

Phase 3 shape:

    START -> retrieve -> grade_documents -> [conditional]
                                             |-- "yes" --> generate
                                             \-- "no"  --> transform_query
                                                            -> web_search_fallback
                                                            -> generate
             generate -> END        (Phase 4 me: -> validate_guardrails -> END)

**Chain kyun nahi, graph kyun:** yahan wo saaf dikhta hai. `grade_documents` ke
baad kaunsa node chalega ye compile time pe fixed nahi — runtime pe state padh ke
decide hota hai. Ek linear chain ye express hi nahi kar sakti.
"""

from langgraph.graph import END, START, StateGraph

from app.nodes import (
    generate,
    grade_documents,
    retrieve,
    transform_query,
    web_search_fallback,
)
from app.schemas.crag_state import CRAGState


def decide_to_generate(state: CRAGState) -> str:
    """Routing function — conditional edge isi ka return value use karta hai.

    Deliberately trivial rakha hai: saara faisla `grade_documents` me hota hai,
    yahan sirf uska result padha jaata hai. Routing logic aur grading logic alag
    rakhne se dono alag-alag test ho sakte hain.

    Default `transform_query` hai (yaani fallback), `generate` nahi — agar
    relevance_score kisi wajah se khaali ho, to safe direction correction path
    hai, na ki unverified context pe answer bol dena.
    """
    return "generate" if state.get("relevance_score") == "yes" else "transform_query"


def build_crag_graph():
    """Compiled graph return karta hai. Module load pe ek baar call hota hai."""
    g = StateGraph(CRAGState)

    g.add_node("retrieve", retrieve.run)
    g.add_node("grade_documents", grade_documents.run)
    g.add_node("transform_query", transform_query.run)
    g.add_node("web_search_fallback", web_search_fallback.run)
    g.add_node("generate", generate.run)

    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "grade_documents")

    g.add_conditional_edges(
        "grade_documents",
        decide_to_generate,
        {"generate": "generate", "transform_query": "transform_query"},
    )

    # Correction path
    g.add_edge("transform_query", "web_search_fallback")
    g.add_edge("web_search_fallback", "generate")

    # Dono branches yahin merge hote hain — do alag generate nodes nahi, kyunki
    # `generate` sirf state["documents"] padhta hai, source se farak nahi padta.
    g.add_edge("generate", END)

    # TODO(Phase 4): generate -> validate_guardrails -> END

    return g.compile()
