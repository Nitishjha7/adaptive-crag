"""Graph routing — CRAG ka asli dil.

Ye tests wo baat pakadte hain jise todna sabse aasan hai aur dhoondhna sabse
mushkil: kaunsa raasta liya gaya, aur state me kya bacha.
"""

from app.schemas.crag_state import initial_state
from tests.conftest import node_order


def test_happy_path_stays_local(graph, fake_llm, fake_search):
    """Grader 'yes' bole -> seedha generate. Web ko haath bhi nahi lagna chahiye."""
    fake_llm.verdict = "yes"

    final = graph.invoke(initial_state("Why does chunk overlap matter?"))

    assert node_order(final) == [
        "retrieve",
        "grade_documents",
        "generate",
        "validate_guardrails",
    ]
    assert final["source_type"] == "vector_db"
    assert fake_search == [], "local hit pe web search bilkul nahi chalna chahiye"
    assert final["documents"], "retrieve ne kuch nahi diya"


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
    # web search ko *rewritten* query milni chahiye, original nahi
    assert fake_search == ["model context protocol spec"]


def test_fallback_replaces_local_docs_instead_of_merging(graph, fake_llm, fake_search):
    """Poore project ka sabse important assertion.

    Local docs abhi "no" grade hue hain. Agar wo web snippets ke saath context me
    bache reh gaye, to CRAG ka poora point khatam — wahi hallucination risk wapas
    aa gaya jise grading step hatane ke liye hai.
    """
    fake_llm.verdict = "no"

    final = graph.invoke(initial_state("What is the Model Context Protocol?"))

    assert len(final["documents"]) == 2, "sirf web snippets bachne chahiye"
    assert all(d.startswith("WEB SNIPPET") for d in final["documents"]), (
        "reject kiye hue local docs abhi bhi context me hain -- replace nahi hua"
    )


def test_search_failure_does_not_crash_the_graph(graph, fake_llm, monkeypatch):
    """Search fail ho jaye (rate limit / network) to graph chalte rehna chahiye.

    Fallback path already ek degraded case hai. Yahan 500 dena demo bhi todta hai
    aur user ko kuch batata bhi nahi.
    """
    import app.nodes.web_search_fallback as node

    def _boom(query, max_results=4):
        raise RuntimeError("simulated rate limit")

    monkeypatch.setattr(node, "web_search", _boom)
    fake_llm.verdict = "no"

    final = graph.invoke(initial_state("What is the Model Context Protocol?"))

    assert "FAILED" in final["logs"][3]
    assert final["documents"] == []
    # generate ko yahan LLM call karni hi nahi chahiye -- context hai hi nahi
    assert "skipped (no documents" in final["logs"][4]
    assert "No context" in final["generation"]


def test_empty_relevance_score_routes_to_correction(graph, fake_llm, fake_search):
    """Grader kuch ajeeb lauta de to safe direction correction path hai.

    Unverified context pe answer bolne se ek extra web call bhugatna behtar hai.
    """
    fake_llm.verdict = "maybe? I'm not sure"

    final = graph.invoke(initial_state("anything"))

    assert final["relevance_score"] == "no"
    assert "transform_query" in node_order(final)


def test_local_route_cites_source_filenames(graph, fake_llm, fake_search):
    """Local answers ke saath citations aani chahiye.

    Metadata me `source` filename ingestion ke time se store ho raha tha, par
    kabhi padha nahi jaata tha — answer tak pahunchta hi nahi tha.
    """
    fake_llm.verdict = "yes"

    final = graph.invoke(initial_state("Why does chunk overlap matter?"))

    assert final["sources"], "local route pe koi citation nahi aayi"
    assert all(s.endswith(".md") for s in final["sources"]), final["sources"]
    assert len(final["sources"]) == len(set(final["sources"])), "duplicate sources"


def test_fallback_replaces_sources_too(graph, fake_llm, monkeypatch):
    """Sabse important citation assertion.

    `documents` ki tarah `sources` bhi replace hone chahiye. Agar local filenames
    bache reh gaye, to UI ek web-sourced answer ke neeche local files cite karega —
    yaani user ko galat jagah bhejega.
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
    """Search fail ho to koi citation nahi — local wale bhi nahi, kyunki wo
    reject ho chuke hain aur unpe koi answer nahi bana."""
    import app.nodes.web_search_fallback as node

    def _boom(query, max_results=4):
        raise RuntimeError("simulated rate limit")

    monkeypatch.setattr(node, "web_search", _boom)
    fake_llm.verdict = "no"

    final = graph.invoke(initial_state("anything"))

    assert final["sources"] == []
