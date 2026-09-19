"""`web_search_fallback` node — the correction path.

Runs only when the grader judged the local context insufficient. Web search is
the **fallback, not the default** — that is what "adaptive" means here.

Searching on every query would make every request pay a network round trip and
extra tokens, throwing away the whole advantage of a local index: a hit is fast
and cheap. The grading call is the price paid to keep the common path fast.
"""

import re
from typing import List

from app.config import get_settings
from app.schemas.crag_state import CRAGState
from app.tools.web_search import web_search

# Search tools append "[source: URL]" to the end of each snippet.
SOURCE_MARKER = re.compile(r"\[source:\s*([^\]]+)\]")


def extract_urls(snippets: List[str]) -> List[str]:
    """Pull the URLs out of the `[source: URL]` markers in snippet text.

    Search tools put the URL inside the snippet text so the LLM can cite it
    inline. A structured citation list needs the same URL separately, hence this
    parse.

    The URL stays in the text too. That looks like duplication but isn't: the one
    in the text is for the model, this list is for the UI. Strip it from the text
    and inline citation dies.
    """
    urls = []
    for snippet in snippets:
        match = SOURCE_MARKER.search(snippet)
        if match:
            urls.append(match.group(1).strip())
    # Two snippets can come from one domain — dedupe while keeping order.
    return list(dict.fromkeys(urls))


def run(state: CRAGState) -> dict:
    # The rewritten query from transform_query; fall back to the original.
    query = state.get("transformed_query") or state["question"]
    max_results = get_settings().TOP_K

    try:
        snippets = web_search(query, max_results=max_results)
    except Exception as exc:  # noqa: BLE001 — see the note below
        # A failed search (rate limit, network, missing key) is recoverable, and
        # all three want the same behaviour. `generate` will say plainly that it
        # found no context. Raising here would 500 the whole request and stop a
        # demo dead. The failure is not silent: it lands in the trace as FAILED
        # and the UI renders that step as failed.
        return {
            "documents": [],
            # Drop the local filenames too — those documents were rejected, so
            # citing them would be wrong.
            "sources": [],
            "source_type": "web_search",
            "logs": [f"web_search_fallback -> FAILED ({type(exc).__name__}: {exc})"],
        }

    return {
        # Replace, not merge. The local documents were just graded "no"; keeping
        # them would dilute the good context and bring back the hallucination
        # risk that the grading step exists to remove. There is a test asserting
        # they do not survive (tests/test_routing.py).
        "documents": snippets,
        "sources": extract_urls(snippets),
        "source_type": "web_search",
        "logs": [f"web_search_fallback -> {len(snippets)} snippets for {query!r}"],
    }
