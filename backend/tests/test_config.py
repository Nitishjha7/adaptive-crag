"""`get_llm()` — the fallback gateway.

No real Groq calls here: what is under test is whether `get_llm` wires a
`with_fallbacks()` chain when `LLM_FALLBACK_MODELS` is set, and stays a plain
client when it is not. Whether the fallback model itself is any good belongs
to the eval harness, not here.
"""

import pytest

from app.config import Settings, get_llm


@pytest.fixture(autouse=True)
def _clear_cache():
    """`get_llm` and `get_settings` are `@lru_cache`'d process-wide — a test
    that mutates env and doesn't clear the cache would leak its client into
    the next test."""
    get_llm.cache_clear()
    yield
    get_llm.cache_clear()


def _settings(**overrides) -> Settings:
    base = {"GROQ_API_KEY": "test-key", "LLM_MODEL": "openai/gpt-oss-120b"}
    base.update(overrides)
    return Settings(**base)


def test_no_fallback_configured_returns_plain_client(monkeypatch):
    import app.config as config

    monkeypatch.setattr(config, "get_settings", lambda: _settings())
    llm = get_llm(temperature=0.0)

    # A plain ChatGroq, not a RunnableWithFallbacks — no `.fallbacks` attribute.
    assert not hasattr(llm, "fallbacks")
    assert llm.model_name == "openai/gpt-oss-120b"


def test_fallback_models_configured_returns_fallback_chain(monkeypatch):
    import app.config as config

    monkeypatch.setattr(
        config,
        "get_settings",
        lambda: _settings(LLM_FALLBACK_MODELS="openai/gpt-oss-20b"),
    )
    llm = get_llm(temperature=0.0)

    assert hasattr(llm, "fallbacks"), "LLM_FALLBACK_MODELS set but no fallback chain built"
    assert llm.runnable.model_name == "openai/gpt-oss-120b"
    assert [f.model_name for f in llm.fallbacks] == ["openai/gpt-oss-20b"]


def test_fallback_list_excludes_primary_model(monkeypatch):
    """The primary appearing in its own fallback list would retry itself —
    pointless, and it would hide a real fallback misconfiguration."""
    import app.config as config

    monkeypatch.setattr(
        config,
        "get_settings",
        lambda: _settings(
            LLM_FALLBACK_MODELS="openai/gpt-oss-120b,openai/gpt-oss-20b"
        ),
    )
    llm = get_llm(temperature=0.0)

    assert [f.model_name for f in llm.fallbacks] == ["openai/gpt-oss-20b"]


def test_temperature_propagates_to_every_client_in_the_chain(monkeypatch):
    """Grading and routing need temp=0 determinism regardless of which model
    in the chain actually answers — a fallback that quietly ran warmer would
    undermine the whole "deterministic grader" claim in grade_documents.py.

    `ChatGroq` clamps an exact 0.0 to a tiny epsilon (1e-08) internally —
    that is its own normalisation, not a gateway bug, so the assertion checks
    "effectively zero" rather than an exact float equality.
    """
    import app.config as config

    monkeypatch.setattr(
        config,
        "get_settings",
        lambda: _settings(LLM_FALLBACK_MODELS="openai/gpt-oss-20b"),
    )
    llm = get_llm(temperature=0.0)

    assert llm.runnable.temperature < 1e-6
    assert llm.fallbacks[0].temperature < 1e-6


def test_missing_api_key_raises(monkeypatch):
    import app.config as config

    monkeypatch.setattr(config, "get_settings", lambda: _settings(GROQ_API_KEY=""))

    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        get_llm(temperature=0.0)
