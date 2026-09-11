"""DuckDuckGo search wrapper — **no API key required**.

The default provider. Its snippets are thinner than Tavily's and it throttles
without warning, but zero signup means the project runs on day one. Swap with
`SEARCH_PROVIDER=tavily` once a key exists.

The interface is identical to `tavily_search` — `(query, max_results) ->
List[str]` — so changing provider changes nothing in the node.
"""

from typing import List


def duckduckgo_search(query: str, max_results: int = 4) -> List[str]:
    """Returns web snippets in the same shape as local chunks."""
    # `ddgs` is the current package name (it was `duckduckgo-search`). Support
    # both so a version drift does not break the import.
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
