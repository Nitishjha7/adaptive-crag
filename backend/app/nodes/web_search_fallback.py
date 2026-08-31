"""`web_search_fallback` node — project ka core #2.

Sirf tab chalta hai jab grader ne local context ko "no" bola ho. Web search
**default nahi, fallback hai** — yahi "Adaptive" ka matlab hai.

Har query pe web search karte to har request ek network round-trip aur zyada
tokens pay karti, aur local index ka poora fayda (fast + sasta hit) khatam ho
jaata. Grading call wahi keemat hai jo common path ko fast rakhne ke liye di jaati hai.
"""

from app.config import get_settings
from app.schemas.crag_state import CRAGState
from app.tools.tavily_search import tavily_search


def run(state: CRAGState) -> dict:
    # transform_query se rewritten query; na mile to original question.
    query = state.get("transformed_query") or state["question"]
    max_results = get_settings().TOP_K

    try:
        snippets = tavily_search(query, max_results=max_results)
    except Exception as exc:  # noqa: BLE001 — deliberately broad, neeche dekh
        # Search fail hona (rate limit, network, missing key) recoverable hai:
        # `generate` khaali documents pe saaf "context nahi mila" bolta hai.
        # Yahan crash karne se poora request 500 ho jaata aur demo ruk jaata.
        return {
            "documents": [],
            "source_type": "web_search",
            "logs": [f"web_search_fallback -> FAILED ({type(exc).__name__}: {exc})"],
        }

    return {
        # Replace, merge nahi. Local docs abhi "no" grade ho chuke hain — unko
        # rakhna acche web context ko dilute karta aur wahi hallucination risk
        # wapas laata jise grading step hatane ke liye hai.
        "documents": snippets,
        "source_type": "web_search",
        "logs": [f"web_search_fallback -> {len(snippets)} snippets for {query!r}"],
    }
