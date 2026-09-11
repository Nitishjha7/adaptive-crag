"""A thin abstraction over the search provider.

The `web_search_fallback` node searches through this and never learns whether
DuckDuckGo or Tavily is underneath. The provider is chosen by the
`SEARCH_PROVIDER` env var, not in code.

**Why the layer:** DuckDuckGo needs no key, so the project runs on day one;
Tavily returns cleaner snippets but wants a signup. One interface makes switching
an env var, and lets the tests mock the entire search layer in a line.
"""

from typing import List

from app.config import get_settings


def web_search(query: str, max_results: int = 4) -> List[str]:
    """Snippets from the configured provider. An unknown provider fails loudly."""
    provider = (get_settings().SEARCH_PROVIDER or "duckduckgo").strip().lower()

    if provider == "tavily":
        from app.tools.tavily_search import tavily_search

        return tavily_search(query, max_results=max_results)

    if provider in {"duckduckgo", "ddg"}:
        from app.tools.duckduckgo_search import duckduckgo_search

        return duckduckgo_search(query, max_results=max_results)

    raise ValueError(
        f"Unknown SEARCH_PROVIDER={provider!r}. Use 'duckduckgo' or 'tavily'."
    )
