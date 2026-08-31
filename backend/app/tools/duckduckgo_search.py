"""DuckDuckGo search wrapper — **koi API key nahi chahiye**.

Default search provider. Tavily ke muqable snippets patle hote hain aur DDG bina
warning ke throttle karta hai, lekin zero signup ka matlab hai project pehle din
se chal jaata hai. Key mil jaye to `SEARCH_PROVIDER=tavily` se swap.

Interface `tavily_search` ke bilkul same hai — `(query, max_results) -> List[str]` —
taaki provider badalne pe node me kuch na badle.
"""

from typing import List


def duckduckgo_search(query: str, max_results: int = 4) -> List[str]:
    """Web snippets return karta hai. Same shape jo local chunks ki hai."""
    # `ddgs` naya package name hai (pehle `duckduckgo-search` tha). Dono support
    # karte hain taaki version drift pe import na toote.
    try:
        from ddgs import DDGS
    except ImportError:  # pragma: no cover
        from duckduckgo_search import DDGS

    snippets = []
    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=max_results):
            body = (item.get("body") or "").strip()
            if not body:
                continue
            url = item.get("href") or item.get("url") or ""
            snippets.append(f"{body}\n[source: {url}]" if url else body)

    return snippets
