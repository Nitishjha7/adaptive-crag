"""Tavily client wrapper.

Node ko clean interface deta hai: query in, `List[str]` snippets out — wahi shape
jo local chunks ki hai. Isliye `generate` ko farak nahi padta ki context Chroma se
aaya ya web se.

**Tavily kyun, raw scraping kyun nahi:** Tavily LLM-optimized snippet text deta hai,
raw HTML nahi. Grounding ke liye clean text chahiye — nav bars aur cookie banners
context window kha jaate hain aur generation ko dilute karte hain.
"""

from typing import List

from app.config import get_settings


def tavily_search(query: str, max_results: int = 4) -> List[str]:
    """Web snippets return karta hai. Failure pe khaali list, exception nahi.

    Network / rate-limit / key error pe crash karna galat hai: fallback path
    already "local context kaafi nahi tha" wala degraded case hai. `generate`
    khaali documents handle karta hai aur saaf bolta hai ki context nahi mila —
    ye 500 se behtar user experience hai aur demo bhi nahi todta.
    """
    s = get_settings()
    if not s.TAVILY_API_KEY:
        raise RuntimeError(
            "TAVILY_API_KEY set nahi hai. Repo root ki `.env` me daal "
            "(https://tavily.com se free key milti hai)."
        )

    from tavily import TavilyClient

    client = TavilyClient(api_key=s.TAVILY_API_KEY)
    response = client.search(
        query=query,
        max_results=max_results,
        search_depth="basic",  # "advanced" zyada accurate hai par slow + mehnga
    )

    snippets = []
    for item in response.get("results", []):
        content = (item.get("content") or "").strip()
        if not content:
            continue
        # URL saath rakhte hain — guardrails/citation ke kaam aata hai aur demo me
        # dikhta hai ki answer sach me web se aaya.
        url = item.get("url", "")
        snippets.append(f"{content}\n[source: {url}]" if url else content)

    return snippets
