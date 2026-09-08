"""`web_search_fallback` node — project ka core #2.

Sirf tab chalta hai jab grader ne local context ko "no" bola ho. Web search
**default nahi, fallback hai** — yahi "Adaptive" ka matlab hai.

Har query pe web search karte to har request ek network round-trip aur zyada
tokens pay karti, aur local index ka poora fayda (fast + sasta hit) khatam ho
jaata. Grading call wahi keemat hai jo common path ko fast rakhne ke liye di jaati hai.
"""

import re
from typing import List

from app.config import get_settings
from app.schemas.crag_state import CRAGState
from app.tools.web_search import web_search

# Search tools snippet ke end me "[source: URL]" daalte hain.
SOURCE_MARKER = re.compile(r"\[source:\s*([^\]]+)\]")


def extract_urls(snippets: List[str]) -> List[str]:
    """Snippet text me se `[source: URL]` marker nikaal ke URLs alag karta hai.

    Search tools URL ko snippet ke text ke andar hi daalte hain, taaki LLM answer
    me inline cite kar sake. Structured citation list ke liye wahi URL alag se
    chahiye — isliye parse karke nikalte hain.

    URL text me bhi rehta hai (duplicate lagta hai, par hai nahi): text wala LLM
    ke liye hai, ye list UI ke liye. Text se hatane pe inline citation mar jaati.
    """
    urls = []
    for snippet in snippets:
        match = SOURCE_MARKER.search(snippet)
        if match:
            urls.append(match.group(1).strip())
    # Ek hi domain se do snippets aa sakte hain — order rakh ke dedupe.
    return list(dict.fromkeys(urls))


def run(state: CRAGState) -> dict:
    # transform_query se rewritten query; na mile to original question.
    query = state.get("transformed_query") or state["question"]
    max_results = get_settings().TOP_K

    try:
        snippets = web_search(query, max_results=max_results)
    except Exception as exc:  # noqa: BLE001 — deliberately broad, neeche dekh
        # Search fail hona (rate limit, network, missing key) recoverable hai:
        # `generate` khaali documents pe saaf "context nahi mila" bolta hai.
        # Yahan crash karne se poora request 500 ho jaata aur demo ruk jaata.
        return {
            "documents": [],
            # Local filenames bhi hata dete hain — wo docs reject ho chuke hain,
            # unko cite karna galat hoga.
            "sources": [],
            "source_type": "web_search",
            "logs": [f"web_search_fallback -> FAILED ({type(exc).__name__}: {exc})"],
        }

    return {
        # Replace, merge nahi. Local docs abhi "no" grade ho chuke hain — unko
        # rakhna acche web context ko dilute karta aur wahi hallucination risk
        # wapas laata jise grading step hatane ke liye hai.
        "documents": snippets,
        "sources": extract_urls(snippets),
        "source_type": "web_search",
        "logs": [f"web_search_fallback -> {len(snippets)} snippets for {query!r}"],
    }
