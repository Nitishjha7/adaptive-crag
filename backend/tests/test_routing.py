"""Graph routing — the heart of CRAG.

These tests catch the thing that is easiest to break and hardest to notice: which
path was taken, and what survived in state.
"""

from app.schemas.crag_state import initial_state
from tests.conftest import node_order


def test_happy_path_stays_local(graph, fake_llm, fake_search):
    """Grader says 'yes' -> straight to generate. Web must not be touched."""
    fake_llm.verdict = "yes"

    final = graph.invoke(initial_state("Why does chunk overlap matter?"))

    assert node_order(final) == [
        "retrieve",
        "grade_documents",
        "generate",
        "validate_guardrails",
    ]
    assert final["source_type"] == "vector_db"
    assert fake_search == [], "web search must not run on a local hit"
    assert final["documents"], "retrieve returned nothing"


def test_correction_path_goes_to_web(graph, fake_llm, fake_search):
    """Grader 'no' bole -> transform -> web -> generate."""
    fake_llm.verdict = "no"
    fake_llm.rewrite = "model context protocol spec"

    final = graph.invoke(initial_state("What is the Model Context Protocol?"))

    assert node_order(final) == [
        "retrieve",
        "grade_documents",
        "transform_query",
        "web_search_fallback",
        "generate",
        "validate_guardrails",
    ]
    assert final["source_type"] == "web_search"
    assert final["transformed_query"] == "model context protocol spec"
    # web search must receive the *rewritten* query, not the original
    assert fake_search == ["model context protocol spec"]


def test_fallback_replaces_local_docs_instead_of_merging(graph, fake_llm, fake_search):
    """The most important assertion in the project.

    The local documents were just graded "no". If they survived in context
    alongside the web snippets, the whole point of CRAG is gone — the very
    hallucination risk the grading step exists to remove is back.
    """
    fake_llm.verdict = "no"

    final = graph.invoke(initial_state("What is the Model Context Protocol?"))

    assert len(final["documents"]) == 2, "only the web snippets should remain"
    assert all(d.startswith("WEB SNIPPET") for d in final["documents"]), (
        "rejected local docs are still in context -- they were merged, not replaced"
    )


def test_search_failure_does_not_crash_the_graph(graph, fake_llm, monkeypatch):
    """If search fails (rate limit, network), the graph must keep running.

    The fallback path is already the degraded case. A 500 here breaks the demo and
    tells the user nothing.
    """
    import app.nodes.web_search_fallback as node

    def _boom(query, max_results=4):
        raise RuntimeError("simulated rate limit")

    monkeypatch.setattr(node, "web_search", _boom)
    fake_llm.verdict = "no"

    final = graph.invoke(initial_state("What is the Model Context Protocol?"))

    assert "FAILED" in final["logs"][3]
    assert final["documents"] == []
    # generate must not make an LLM call here -- there is no context at all
    assert "skipped (no documents" in final["logs"][4]
    assert "No context" in final["generation"]


def test_empty_relevance_score_routes_to_correction(graph, fake_llm, fake_search):
    """If the grader returns something odd, the safe direction is the correction
    path.

    Paying for one extra web call beats answering from unverified context.
    """
    fake_llm.verdict = "maybe? I'm not sure"

    final = graph.invoke(initial_state("anything"))

    assert final["relevance_score"] == "no"
    assert "transform_query" in node_order(final)


def test_local_route_cites_source_filenames(graph, fake_llm, fake_search):
    """Local answers must arrive with citations.

    The `source` filename had been stored in metadata since ingestion but was
    never read — it never reached the answer.
    """
    fake_llm.verdict = "yes"

    final = graph.invoke(initial_state("Why does chunk overlap matter?"))

    assert final["sources"], "no citations came back on the local route"
    assert all(s.endswith(".md") for s in final["sources"]), final["sources"]
    assert len(final["sources"]) == len(set(final["sources"])), "duplicate sources"


def test_fallback_replaces_sources_too(graph, fake_llm, monkeypatch):
    """The most important citation assertion.

    Like `documents`, `sources` must be replaced. If local filenames survived, the
    UI would cite local files under a web-sourced answer — sending the user to the
    wrong place.
    """
    import app.nodes.web_search_fallback as node

    monkeypatch.setattr(
        node,
        "web_search",
        lambda q, max_results=4: [
            "Some web content.\n[source: https://example.com/a]",
            "More web content.\n[source: https://example.com/b]",
        ],
    )
    fake_llm.verdict = "no"

    final = graph.invoke(initial_state("What is the Model Context Protocol?"))

    assert final["sources"] == [
        "https://example.com/a",
        "https://example.com/b",
    ], final["sources"]
    assert not any(s.endswith(".md") for s in final["sources"]), (
        "reject kiye hue local docs abhi bhi cite ho rahe hain"
    )


def test_search_failure_clears_sources(graph, fake_llm, monkeypatch):
    """If search fails there are no citations — not even the local ones, because
    they were rejected and no answer was built on them."""
    import app.nodes.web_search_fallback as node

    def _boom(query, max_results=4):
        raise RuntimeError("simulated rate limit")

    monkeypatch.setattr(node, "web_search", _boom)
    fake_llm.verdict = "no"

    final = graph.invoke(initial_state("anything"))

    assert final["sources"] == []
