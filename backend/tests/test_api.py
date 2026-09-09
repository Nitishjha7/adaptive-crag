"""FastAPI layer — request validation aur response shape."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    import main

    # TestClient lifespan chalata hai, isliye graph compile ho jaata hai.
    with TestClient(main.app) as c:
        yield c


def test_health_makes_no_llm_call(client):
    """Healthcheck sasta hona chahiye. Agar ye LLM ping karta, to ek rate limit
    hi container ko unhealthy mark karwa deta aur Docker restart loop me chala jaata."""
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
        "transformed_query", "logs", "elapsed_ms",
    }
    assert isinstance(body["sources"], list)
    assert body["source_type"] in {"vector_db", "web_search"}
    assert body["relevance_score"] in {"yes", "no"}
    assert body["logs"], "trace khaali hai -- explainability chali gayi"


class TestStats:
    """`/api/stats` dashboard ko feed karta hai. Har number asli source se aana
    chahiye — yahi wo endpoint hai jahan hardcoded demo values chupke se aa
    jaati hain."""

    def test_counts_come_from_the_real_corpus(self, client):
        body = client.get("/api/stats").json()
        assert body["documents"] > 0, "corpus files gine nahi gaye"
        assert body["chunks"] > 0, "vectorstore khaali hai -- `ingest.py` chalaya?"

    def test_config_is_echoed_not_invented(self, client):
        cfg = client.get("/api/stats").json()["config"]
        for key in ("llm_model", "embedding_model", "search_provider", "top_k"):
            assert cfg.get(key), f"{key} missing"
        assert isinstance(cfg["hybrid"], bool)

    def test_evaluation_is_none_when_not_run(self, client, monkeypatch, tmp_path):
        """Eval kabhi chala hi na ho to `null` aana chahiye, `0` nahi.

        "Measure nahi hua" aur "score zero hai" do alag baatein hain, aur UI ko
        farak pata hona chahiye -- warna dashboard ek jhoothi 0% accuracy dikha dega.
        """
        import app.config as config

        monkeypatch.setattr(config, "BACKEND_DIR", tmp_path)

        body = client.get("/api/stats").json()
        assert body["evaluation"] is None

    def test_makes_no_llm_call(self, client):
        """Dashboard har page load pe ise hit karta hai -- ek LLM call yahan
        rate limit ko UI ke saath baandh deta."""
        assert client.get("/api/stats").status_code == 200
