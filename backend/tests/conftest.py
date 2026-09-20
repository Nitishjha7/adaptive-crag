"""Shared fixtures — the LLM is replaced with a fake.

**Why no real LLM calls here:** these tests exercise control flow, not model
quality. Real calls would be slow, cost money, require an API key and be
non-deterministic — flaky in CI. Scripting the grader's verdict is exactly the
thing under test: "if the grader says no, does the graph take the right path?"

The grader's *accuracy* is a different question, and it belongs to the eval
harness, not to these tests.
"""

import os

import pytest
from langchain_core.runnables import RunnableLambda

# The rate limiter is per-process and keys on the client address, so the whole
# suite shares one bucket: the sixth test to post an upload would get a 429 for
# reasons that have nothing to do with what it asserts. A dedicated test turns
# it back on to check it works.
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")


@pytest.fixture
def client():
    """The FastAPI app under TestClient, with the lifespan run so the graph is
    compiled. Lives here rather than in test_api.py because several modules
    need it."""
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app) as c:
        yield c


class _Msg:
    """A minimal stand-in for LangChain's AIMessage — nodes only ever read `.content`."""

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
        """Build a `get_llm` replacement that returns the reply held in `attr`."""
        return lambda temperature=0.0: RunnableLambda(
            lambda _prompt: _Msg(getattr(self, attr))
        )


@pytest.fixture
def fake_llm(monkeypatch):
    """Patch every LLM call site and hand back a controller object.

    monkeypatch so it unwinds after the test — otherwise one test's patch leaks
    into the next.
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
    """Replace web search with deterministic snippets.

    Real search depends on the network and its results change daily — a routing
    test cannot stand on that. A separate test covers real search.
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
    """Pulls just the node names out of the trace logs, so assertions stay readable."""
    return [line.split(" ->")[0] for line in final_state["logs"]]
