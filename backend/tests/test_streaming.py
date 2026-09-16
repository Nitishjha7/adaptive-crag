"""`run_query_stream` and `/api/query/stream` — SSE built on `graph.stream()`.

No real LLM or web calls: `fake_llm`/`fake_search` (tests/conftest.py) script
the same node replies the routing tests use, so what is under test is the
event sequence and the final-payload parity with `/api/query`, not model
quality.
"""

import json

import pytest


def _collect(question):
    from app.graph.build_graph import run_query_stream

    return list(run_query_stream(question))


def test_local_route_emits_progress_then_done(fake_llm, fake_search):
    fake_llm.verdict = "yes"

    events = _collect("Why does chunk overlap matter?")
    kinds = [kind for kind, _ in events]
    nodes = [payload["node"] for kind, payload in events if kind == "progress"]

    assert kinds == ["progress", "progress", "progress", "progress", "done"]
    assert nodes == ["retrieve", "grade_documents", "generate", "validate_guardrails"]
    assert fake_search == [], "web search must not run on a local hit"


def test_web_fallback_route_emits_the_full_correction_sequence(fake_llm, fake_search):
    fake_llm.verdict = "no"
    fake_llm.rewrite = "model context protocol spec"

    events = _collect("What is the Model Context Protocol?")
    nodes = [payload["node"] for kind, payload in events if kind == "progress"]

    assert nodes == [
        "retrieve",
        "grade_documents",
        "transform_query",
        "web_search_fallback",
        "generate",
        "validate_guardrails",
    ]
    assert fake_search == ["model context protocol spec"]


def test_grade_documents_progress_label_states_the_routing_decision(fake_llm, fake_search):
    """The corrective routing decision is this project's actual story — the
    progress event has to say what was decided, not just which node ran."""
    fake_llm.verdict = "no"

    events = _collect("What is the Model Context Protocol?")
    grade_event = next(p for k, p in events if k == "progress" and p["node"] == "grade_documents")

    assert "relevance=no" in grade_event["label"]
    assert "web" in grade_event["label"]


def test_retrieve_progress_label_reports_chunk_count(fake_llm, fake_search):
    fake_llm.verdict = "yes"

    events = _collect("Why does chunk overlap matter?")
    retrieve_event = next(p for k, p in events if k == "progress" and p["node"] == "retrieve")

    assert "chunk" in retrieve_event["label"]


def test_final_done_event_carries_full_state(fake_llm, fake_search):
    fake_llm.verdict = "yes"

    events = _collect("Why does chunk overlap matter?")
    kind, final_state = events[-1]

    assert kind == "done"
    assert final_state["relevance_score"] == "yes"
    assert final_state.get("final_output") or final_state.get("generation")


def test_stream_endpoint_matches_non_streaming_payload_shape(client, fake_llm, fake_search):
    """The final SSE event must be exactly what /api/query returns for the
    same question — a streamed result quietly disagreeing with the
    non-streamed one would be worse than not streaming at all."""
    fake_llm.verdict = "yes"
    question = "Why does chunk overlap matter?"

    non_streamed = client.post("/api/query", json={"question": question}).json()

    with client.stream("POST", "/api/query/stream", json={"question": question}) as r:
        assert r.status_code == 200
        lines = list(r.iter_lines())

    events = []
    current_event = None
    for line in lines:
        if line.startswith("event: "):
            current_event = line[len("event: "):]
        elif line.startswith("data: "):
            events.append((current_event, json.loads(line[len("data: "):])))

    kinds = [kind for kind, _ in events]
    assert "progress" in kinds
    assert kinds[-1] == "done"

    done_payload = events[-1][1]
    # elapsed_ms will differ between the two calls -- everything else must match.
    assert {k: v for k, v in done_payload.items() if k != "elapsed_ms"} == {
        k: v for k, v in non_streamed.items() if k != "elapsed_ms"
    }


@pytest.fixture
def client():
    import main

    from fastapi.testclient import TestClient

    with TestClient(main.app) as c:
        yield c
