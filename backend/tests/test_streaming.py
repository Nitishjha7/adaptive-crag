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


# --------------------------------------------------------------------------- #
# Does it actually stream?
# --------------------------------------------------------------------------- #
#
# Everything above asserts the event *sequence* and the final payload, and all
# of it passed while the endpoint was not streaming at all: `event_source`
# awaited the producer to completion before draining the queue, so every event
# was emitted in one burst at the end. Measured against the running server,
# `retrieve` reported elapsed_ms=2229 but reached the client at ~8.5s with
# everything else.
#
# `TestClient` cannot catch that. It buffers the whole response body before
# handing it back, so a burst at the end and a proper trickle look identical to
# it - which is exactly why the bug survived a suite that already had five
# streaming tests. This one runs a real uvicorn server in a thread and measures
# when bytes actually arrive.


def test_first_event_arrives_before_the_query_finishes():
    """The first progress event must reach the client while the graph is still
    running, not after it has finished.

    A deliberately slow `generate` node widens the gap: with real streaming the
    `retrieve` event lands almost immediately and `done` lands after the delay,
    so first-event time is a small fraction of total time. With the producer
    awaited to completion both land together and the ratio collapses to ~1.
    """
    import threading
    import time

    import httpx
    import uvicorn

    import app.guardrails.validators as validators
    import app.nodes.generate as generate
    import app.nodes.grade_documents as grade_documents
    import app.nodes.transform_query as transform_query
    import app.nodes.web_search_fallback as web_node
    from langchain_core.runnables import RunnableLambda

    from tests.conftest import _Msg

    DELAY = 1.5

    def _reply(text, delay=0.0):
        def _call(_prompt):
            if delay:
                time.sleep(delay)
            return _Msg(text)

        return lambda temperature=0.0: RunnableLambda(_call)

    # Patched on the module objects rather than with monkeypatch: the server
    # runs in another thread in this same process, so plain attribute
    # assignment reaches it. Restored in the finally block below.
    originals = {
        grade_documents: grade_documents.get_llm,
        transform_query: transform_query.get_llm,
        generate: generate.get_llm,
        validators: validators.get_llm,
    }
    original_search = web_node.web_search

    grade_documents.get_llm = _reply("yes")
    transform_query.get_llm = _reply("rewritten")
    generate.get_llm = _reply("an answer", delay=DELAY)
    validators.get_llm = _reply("yes")
    web_node.web_search = lambda query, max_results=4: ["snippet"]

    from main import app as fastapi_app

    config = uvicorn.Config(fastapi_app, host="127.0.0.1", port=8778, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(100):  # wait for the port to open
            if server.started:
                break
            time.sleep(0.05)
        assert server.started, "test server never started"

        started = time.perf_counter()
        first_event_at = None
        with httpx.Client(timeout=60.0) as client:
            with client.stream(
                "POST",
                "http://127.0.0.1:8778/api/query/stream",
                json={"question": "Why does chunk overlap matter?"},
            ) as response:
                assert response.status_code == 200
                for line in response.iter_lines():
                    if line.startswith("data:") and first_event_at is None:
                        first_event_at = time.perf_counter() - started
                total = time.perf_counter() - started
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        for module, fn in originals.items():
            module.get_llm = fn
        web_node.web_search = original_search

    assert first_event_at is not None, "no data event was received"
    # The slow node is 1.5s; the first event comes from `retrieve`, long before
    # it. Buffering would put both at the same moment.
    assert first_event_at < total - (DELAY / 2), (
        f"first event arrived at {first_event_at:.2f}s of a {total:.2f}s "
        "request - the response is buffered, not streamed"
    )
