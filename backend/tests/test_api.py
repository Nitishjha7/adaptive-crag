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
        "answer", "source_type", "relevance_score",
        "transformed_query", "logs", "elapsed_ms",
    }
    assert body["source_type"] in {"vector_db", "web_search"}
    assert body["relevance_score"] in {"yes", "no"}
    assert body["logs"], "trace khaali hai -- explainability chali gayi"
