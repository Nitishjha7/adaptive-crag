"""CRAGState — graph ka single source of truth.

Har node poora state nahi lautata, sirf jo keys badalni hai wahi partial dict me
lautata hai. LangGraph un updates ko merge karta hai.

Merge behaviour per-key **reducer** se decide hoti hai:

- `logs` pe additive reducer — har node ek line append karta hai, kisi node ko
  ye jaanne ki zaroorat nahi ki usse pehle kya chala. Poora execution trace
  free me ban jaata hai (yahi frontend ka TraceViewer render karega).

- `documents` pe **overwrite** (default) — deliberate choice. `retrieve` local
  chunks set karta hai; fallback pe `web_search_fallback` unko **replace** karta
  hai, append nahi. Local docs "no" grade ho chuke hote hain — unhe context me
  rakhna generation ko dilute karta aur wahi hallucination risk wapas laata jise
  grading step hatane ke liye hai.
"""

import operator
from typing import Annotated, List

from typing_extensions import TypedDict


class CRAGState(TypedDict, total=False):
    # --- input -------------------------------------------------------------
    question: str
    """Original user query. Kabhi mutate nahi hota — rewrite alag key me jaata hai."""

    # --- set by transform_query (Phase 3) ----------------------------------
    transformed_query: str
    """Keyword-focused web search query. Sirf fallback path pe bharti hai."""

    # --- working context ---------------------------------------------------
    documents: List[str]
    """Working context. `retrieve` bharta hai, `web_search_fallback` replace karta hai."""

    # --- set by grade_documents (Phase 3) ----------------------------------
    relevance_score: str
    """"yes" | "no" — conditional edge isi pe route karta hai."""

    source_type: str
    """"vector_db" | "web_search" — UI ka source badge isi se."""

    # --- output ------------------------------------------------------------
    generation: str
    """Raw LLM answer, abhi guardrails-checked nahi."""

    final_output: str
    """Guardrails-validated answer — yahi user ko jaata hai."""

    # --- trace -------------------------------------------------------------
    logs: Annotated[List[str], operator.add]
    """Node-by-node execution trace. Additive — har node ek line append karta hai."""


def initial_state(question: str) -> CRAGState:
    """Fresh state banata hai ek query ke liye.

    Ek hi jagah se initialise karna zaroori hai: `logs` ka additive reducer list
    par kaam karta hai, to usko `[]` se start karna hi padta hai (None pe crash).
    """
    return {
        "question": question,
        "transformed_query": "",
        "documents": [],
        "relevance_score": "",
        "source_type": "vector_db",
        "generation": "",
        "final_output": "",
        "logs": [],
    }
