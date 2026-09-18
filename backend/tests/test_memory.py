"""app/memory/ — episodic and semantic memory, backed by real Chroma + FastEmbed.

Unlike test_token_usage.py's fakes, these use the real embedding model — the
same one already loaded for retrieval (test_retrieval.py does the same for
BM25/reranking). Similarity search is the thing under test here, and a fake
embedding would not exercise it. Each test points memory at a fresh temp
directory via `app.memory.store`'s cache, so runs never share state with the
real corpus's vectorstore or with each other.
"""

import pytest

from app.memory import episodic, semantic, store


@pytest.fixture(autouse=True)
def _fresh_memory_dir(tmp_path, monkeypatch):
    # get_settings() is lru_cached (app/config.py), so the cached Settings
    # instance already exists by the time this fixture runs in a shared test
    # session - patching the env var alone would not reach it. Patching the
    # instance attribute directly is what actually takes effect.
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "VECTORSTORE_DIR", str(tmp_path))
    monkeypatch.delenv("DISABLE_MEMORY_STORE", raising=False)
    store.reset_for_tests()
    yield
    store.reset_for_tests()


class TestStore:
    def test_get_memory_store_returns_a_store(self):
        assert store.get_memory_store() is not None

    def test_disabled_by_env_returns_none(self, monkeypatch):
        monkeypatch.setenv("DISABLE_MEMORY_STORE", "true")
        store.reset_for_tests()
        assert store.get_memory_store() is None

    def test_cached_after_first_call(self):
        first = store.get_memory_store()
        second = store.get_memory_store()
        assert first is second


class TestEpisodic:
    def test_recall_similar_empty_when_nothing_recorded(self):
        assert episodic.recall_similar("What is retrieval-augmented generation?") == []

    def test_record_then_recall_finds_a_reworded_question(self):
        episodic.record_episode(
            question="What is retrieval-augmented generation?",
            source_type="vector_db",
            guardrail_passed=True,
        )
        recalled = episodic.recall_similar("Explain retrieval augmented generation")
        assert len(recalled) >= 1
        assert recalled[0]["guardrail_passed"] is True

    def test_unrelated_question_does_not_match(self):
        episodic.record_episode(
            question="What is retrieval-augmented generation?",
            source_type="vector_db",
            guardrail_passed=True,
        )
        recalled = episodic.recall_similar("What is the capital of France?")
        assert recalled == []

    def test_record_episode_from_state_skips_when_no_verdict(self):
        episodic.record_episode_from_state({"question": "x"})
        assert episodic.recall_similar("x") == []

    def test_record_episode_from_state_records_when_verdict_present(self):
        episodic.record_episode_from_state(
            {"question": "What is chunking?", "source_type": "vector_db", "guardrail_passed": False}
        )
        recalled = episodic.recall_similar("What is chunking?")
        assert len(recalled) >= 1
        assert recalled[0]["guardrail_passed"] is False

    def test_recall_fails_open_when_store_disabled(self, monkeypatch):
        monkeypatch.setenv("DISABLE_MEMORY_STORE", "true")
        store.reset_for_tests()
        assert episodic.recall_similar("anything") == []

    def test_format_episodes_for_prompt_empty(self):
        assert episodic.format_episodes_for_prompt([]) == ""

    def test_format_episodes_for_prompt_silent_when_all_passed(self):
        episodes = [{"guardrail_passed": True}, {"guardrail_passed": True}]
        assert episodic.format_episodes_for_prompt(episodes) == ""

    def test_format_episodes_for_prompt_warns_on_failures(self):
        episodes = [{"guardrail_passed": True}, {"guardrail_passed": False}]
        text = episodic.format_episodes_for_prompt(episodes)
        assert "1 of 2" in text


class TestSemantic:
    def test_recall_facts_empty_when_none_recorded(self):
        assert semantic.recall_facts("anything") == []

    def test_consolidate_writes_nothing_below_threshold(self):
        for i in range(semantic._MIN_CLUSTER_SIZE - 1):
            episodic.record_episode(
                question=f"What is vector quantization variant {i}?",
                source_type="vector_db",
                guardrail_passed=False,
            )
        assert semantic.consolidate_facts() == 0

    def test_consolidate_writes_fact_at_threshold(self):
        for i in range(semantic._MIN_CLUSTER_SIZE):
            episodic.record_episode(
                question=f"What is vector quantization variant {i}?",
                source_type="vector_db",
                guardrail_passed=False,
            )
        written = semantic.consolidate_facts()
        assert written >= 1
        facts = semantic.recall_facts("What is vector quantization?")
        assert len(facts) >= 1

    def test_consolidate_ignores_passed_episodes(self):
        for i in range(semantic._MIN_CLUSTER_SIZE):
            episodic.record_episode(
                question=f"What is vector quantization variant {i}?",
                source_type="vector_db",
                guardrail_passed=True,
            )
        assert semantic.consolidate_facts() == 0

    def test_format_facts_for_prompt_empty(self):
        assert semantic.format_facts_for_prompt([]) == ""

    def test_format_facts_for_prompt_lists_each(self):
        text = semantic.format_facts_for_prompt(["fact one", "fact two"])
        assert "fact one" in text and "fact two" in text
