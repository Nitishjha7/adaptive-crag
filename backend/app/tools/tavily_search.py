"""Tavily client wrapper.

Gives the node a clean interface: query in, `List[str]` snippets out — the same
shape as local chunks, so `generate` never has to know whether the context came
from Chroma or the web.

**Why Tavily rather than raw scraping:** it returns LLM-optimised snippet text,
not raw HTML. Grounding needs clean text — nav bars and cookie banners eat the
context window and dilute generation.
"""

from typing import List

from app.config import get_settings


def tavily_search(query: str, max_results: int = 4) -> List[str]:
    """Returns web snippets; an empty list on failure rather than raising.

    Crashing on a network, rate-limit or key error would be wrong: the fallback
    path is already the degraded case of "local context was not enough".
    `generate` handles empty documents and says plainly that it found no context,
    which beats a 500 and does not stop a demo.
    """
    s = get_settings()
    if not s.TAVILY_API_KEY:
        raise RuntimeError(
            "TAVILY_API_KEY is not set. Add it to `.env` in the repo root "
            "(a free key is available at https://tavily.com)."
        )

    from tavily import TavilyClient

    client = TavilyClient(api_key=s.TAVILY_API_KEY)
    response = client.search(
        query=query,
        max_results=max_results,
        search_depth="basic",  # "advanced" is more accurate but slower and pricier
    )

    snippets = []
    for item in response.get("results", []):
        content = (item.get("content") or "").strip()
        if not content:
            continue
        # Keep the URL alongside: citations need it, and in a demo it shows the
        # answer really did come from the web.
        url = item.get("url", "")
        snippets.append(f"{content}\n[source: {url}]" if url else content)

    return snippets
