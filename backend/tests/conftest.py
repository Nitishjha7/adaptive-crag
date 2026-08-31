"""Shared fixtures — LLM ko fake se replace karte hain.

**Yahan asli LLM call kyun nahi:** ye tests control flow ka test hain, model ki
quality ka nahi. Asli calls slow hote, paise lagte, API key maangte, aur
non-deterministic hote — yaani CI me flaky. Grader ko scripted verdict dena hi
wo cheez hai jo hume test karni hai: "agar grader 'no' bole to kya graph sahi
raasta leta hai".

Grader ki *accuracy* alag cheez hai — wo eval harness ka kaam hai (roadmap),
in tests ka nahi.
"""

import pytest
from langchain_core.runnables import RunnableLambda


class _Msg:
    """LangChain ke AIMessage ka minimal stand-in — nodes sirf `.content` padhte hain."""

    def __init__(self, content: str):
        self.content = content


class FakeLLM:
    """Scripted replies. Har node ka reply alag set kar sakte hain."""

    def __init__(self):
        self.verdict = "yes"          # grade_documents
        self.rewrite = "rewritten keyword query"   # transform_query
        self.answer = "A grounded answer."         # generate
        self.grounded = "yes"         # groundedness check

    def factory_for(self, attr: str):
        """`get_llm` ka replacement banata hai jo `attr` wala reply lautaye."""
        return lambda temperature=0.0: RunnableLambda(
            lambda _prompt: _Msg(getattr(self, attr))
        )


@pytest.fixture
def fake_llm(monkeypatch):
    """Saare LLM call sites ko patch karta hai aur controller object deta hai.

    monkeypatch use karte hain taaki test ke baad apne aap undo ho jaye — warna
    ek test ka patch agle test me leak karta.
    """
    import app.guardrails.validators as validators
    import app.nodes.generate as generate
    import app.nodes.grade_documents as grade_documents
    import app.nodes.transform_query as transform_query

    llm = FakeLLM()
    monkeypatch.setattr(grade_documents, "get_llm", llm.factory_for("verdict"))
    monkeypatch.setattr(transform_query, "get_llm", llm.factory_for("rewrite"))
    monkeypatch.setattr(generate, "get_llm", llm.factory_for("answer"))
    monkeypatch.setattr(validators, "get_llm", llm.factory_for("grounded"))
    return llm


@pytest.fixture
def fake_search(monkeypatch):
    """Web search ko deterministic snippets se replace karta hai.

    Asli search network pe depend karta hai aur results roz badalte hain — routing
    test uspe nahi tik sakta. Ek alag test asli search ko cover karta hai.
    """
    import app.nodes.web_search_fallback as node

    calls = []

    def _search(query, max_results=4):
        calls.append(query)
        return [f"WEB SNIPPET {i} for {query!r}" for i in range(1, 3)]

    monkeypatch.setattr(node, "web_search", _search)
    return calls


@pytest.fixture
def graph():
    from app.graph.build_graph import build_crag_graph

    return build_crag_graph()


def node_order(final_state):
    """Trace logs se sirf node ke naam nikalta hai — assertions padhne layak rehti hain."""
    return [line.split(" ->")[0] for line in final_state["logs"]]
