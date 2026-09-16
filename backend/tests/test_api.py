"""FastAPI layer — request validation aur response shape."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    import main

    # TestClient runs the lifespan, so the graph gets compiled.
    with TestClient(main.app) as c:
        yield c


def test_health_makes_no_llm_call(client):
    """A healthcheck has to be cheap. If it pinged the LLM, one rate limit would
    mark the container unhealthy and Docker would restart it in a loop."""
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["indexed_chunks"] > 0, "vectorstore khaali hai -- `ingest.py` chalaya?"
    assert "search_provider" in body


def test_empty_question_rejected(client):
    assert client.post("/api/query", json={"question": ""}).status_code == 422


def test_missing_question_rejected(client):
    assert client.post("/api/query", json={}).status_code == 422


def test_response_shape(client, fake_llm, fake_search):
    r = client.post("/api/query", json={"question": "Why does chunk overlap matter?"})
    assert r.status_code == 200

    body = r.json()
    # Frontend inhi fields pe badge + trace render karega -- shape na toote
    assert set(body) == {
        "answer", "source_type", "sources", "relevance_score",
        "transformed_query", "logs", "elapsed_ms", "token_usage",
    }
    assert isinstance(body["sources"], list)
    assert body["source_type"] in {"vector_db", "web_search"}
    assert body["relevance_score"] in {"yes", "no"}
    assert body["logs"], "trace khaali hai -- explainability chali gayi"
    assert "by_model" in body["token_usage"]
    assert "total_tokens" in body["token_usage"]


class TestStats:
    """`/api/stats` feeds the dashboard. Every number has to come from a real
    source — this is the endpoint where hardcoded demo values would quietly
    jaati hain."""

    def test_counts_come_from_the_real_corpus(self, client):
        body = client.get("/api/stats").json()
        assert body["documents"] > 0, "corpus documents were not counted"
        assert body["chunks"] > 0, "vectorstore khaali hai -- `ingest.py` chalaya?"

    def test_config_is_echoed_not_invented(self, client):
        cfg = client.get("/api/stats").json()["config"]
        for key in ("llm_model", "embedding_model", "search_provider", "top_k"):
            assert cfg.get(key), f"{key} missing"
        assert isinstance(cfg["hybrid"], bool)

    def test_evaluation_is_none_when_not_run(self, client, monkeypatch, tmp_path):
        """If the eval never ran, this must be `null`, not `0`.

        "Not measured" and "scored zero" are different claims, and the UI has to
        be able to tell them apart -- otherwise the dashboard shows a false 0%.
        """
        import app.config as config

        monkeypatch.setattr(config, "BACKEND_DIR", tmp_path)

        body = client.get("/api/stats").json()
        assert body["evaluation"] is None

    def test_makes_no_llm_call(self, client):
        """The dashboard hits this on every page load -- one LLM call here
        rate limit ko UI ke saath baandh deta."""
        assert client.get("/api/stats").status_code == 200


class TestMetrics:
    """`/metrics` — the Prometheus scrape target."""

    def test_returns_prometheus_text_format(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200
        assert "text/plain" in r.headers["content-type"]

    def test_query_updates_the_exposed_metrics(self, client, fake_llm, fake_search):
        client.post("/api/query", json={"question": "Why does chunk overlap matter?"})
        body = client.get("/metrics").text
        assert "crag_queries_total" in body
        assert "crag_llm_calls_total" in body
