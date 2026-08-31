"""Search provider ke upar ek patli abstraction.

`web_search_fallback` node yahin se search karta hai — usse pata nahi hota ki
neeche DuckDuckGo hai ya Tavily. Provider `SEARCH_PROVIDER` env var se badalta
hai, code se nahi.

**Ye layer kyun:** DuckDuckGo bina key ke chalta hai (project din ek se chalu),
Tavily behtar snippets deta hai par signup maangta hai. Ek hi interface hone se
dono ke beech switch karna ek env var ka kaam hai, aur test me poora search layer
ek line se mock ho jaata hai.
"""

from typing import List

from app.config import get_settings


def web_search(query: str, max_results: int = 4) -> List[str]:
    """Configured provider se snippets. Provider galat ho to saaf error."""
    provider = (get_settings().SEARCH_PROVIDER or "duckduckgo").strip().lower()

    if provider == "tavily":
        from app.tools.tavily_search import tavily_search

        return tavily_search(query, max_results=max_results)

    if provider in {"duckduckgo", "ddg"}:
        from app.tools.duckduckgo_search import duckduckgo_search

        return duckduckgo_search(query, max_results=max_results)

    raise ValueError(
        f"SEARCH_PROVIDER={provider!r} pehchana nahi gaya. 'duckduckgo' ya 'tavily' use kar."
    )
