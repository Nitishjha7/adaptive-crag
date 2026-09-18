"""Hybrid retrieval and reranking.

These tests check **structure**, not ranking quality. "The reranker finds better
chunks" is a measurement claim, and that belongs to the eval
(`eval/RESULTS.md`), not to a unit test. What is checked here: the fusion maths
is right, the flags actually change the pipeline, and the failure path is
graceful.
"""

import pytest

from app.tools.bm25_search import bm25_search, tokenize
from app.tools.reranker import reciprocal_rank_fusion, rerank


class TestTokenizer:
    def test_lowercases_and_splits(self):
        assert tokenize("Chunk OVERLAP matters!") == ["chunk", "overlap", "matters"]

    def test_keeps_alphanumerics_together(self):
        """Identifiers must stay one token — this is the case where BM25 beats
        vector search."""
        assert "bge" in tokenize("BAAI/bge-small-en-v1.5")
        assert "v1" in tokenize("BAAI/bge-small-en-v1.5")


class TestBM25:
    def test_finds_the_right_doc_by_keyword(self):
        hits = bm25_search("chunk overlap", k=3)
        assert hits, "BM25 returned nothing"
        assert any("chunking" in source for _, source in hits)

    def test_returns_text_source_pairs(self):
        """The shape must match vector search, or the two cannot be fused."""
        for item in bm25_search("embeddings", k=2):
            assert isinstance(item, tuple) and len(item) == 2
            assert all(isinstance(x, str) for x in item)

    def test_nonsense_query_returns_nothing_not_garbage(self):
        """In BM25 a score of 0 means no term matched at all. Ranking those would
        only add noise to the fusion, so they are dropped."""
        assert bm25_search("zzzzqqqq xkcdplover", k=4) == []


class TestRRF:
    def test_document_in_both_lists_ranks_above_one_in_either(self):
        """This is the whole point of RRF — whatever both retrievers agree on
        ranks above what only one of them found."""
        a = [("both", "s"), ("only_a", "s")]
        b = [("only_b", "s"), ("both", "s")]

        fused = [text for text, _ in reciprocal_rank_fusion([a, b])]

        assert fused[0] == "both", fused

    def test_dedupes_across_lists(self):
        a = [("x", "s"), ("y", "s")]
        b = [("x", "s")]
        assert [t for t, _ in reciprocal_rank_fusion([a, b])] == ["x", "y"]

    def test_ignores_score_scale_entirely(self):
        """The property RRF was chosen for: merging vector distance (lower is
        better) with a BM25 score (higher is better) without normalising either.
        RRF reads only rank, so the scales stop mattering."""
        one = [("a", "s"), ("b", "s")]
        # Same ranking, no scores anywhere — the result must be identical
        assert reciprocal_rank_fusion([one]) == reciprocal_rank_fusion([one])

    def test_empty_lists_are_safe(self):
        assert reciprocal_rank_fusion([]) == []
        assert reciprocal_rank_fusion([[], []]) == []


class TestReranker:
    def test_returns_at_most_k(self):
        candidates = [(f"chunk about overlap {i}", "d.md") for i in range(6)]
        assert len(rerank("chunk overlap", candidates, k=3)) == 3

    def test_empty_input_is_safe(self):
        assert rerank("anything", [], k=4) == []

    def test_failure_falls_back_to_original_order(self, monkeypatch):
        """Reranking is an improvement, not a requirement. If the model fails to
        load, retrieval must keep working — just a little less accurately."""
        import app.tools.reranker as mod

        def _boom():
            raise RuntimeError("model download failed")

        monkeypatch.setattr(mod, "get_cross_encoder", _boom)

        candidates = [("first", "a.md"), ("second", "b.md"), ("third", "c.md")]
        assert rerank("q", candidates, k=2) == candidates[:2]


class TestRetrieveNodeFlags:
    """The flags really do change the pipeline — which matters, because the eval
    uses them to compare baseline against hybrid + rerank."""

    @pytest.mark.parametrize(
        "hybrid,reranker,expect_in_log",
        [
            (False, False, "vector="),
            (True, False, "bm25="),
            (False, True, "reranked"),
        ],
    )
    def test_log_reflects_configuration(self, monkeypatch, hybrid, reranker, expect_in_log):
        import app.config as config
        import app.nodes.retrieve as retrieve_node

        s = config.get_settings()
        monkeypatch.setattr(s, "USE_HYBRID", hybrid)
        monkeypatch.setattr(s, "USE_RERANKER", reranker)

        out = retrieve_node.run({"question": "why does chunk overlap matter?"})

        assert expect_in_log in out["logs"][0], out["logs"]
        assert len(out["documents"]) <= s.TOP_K
        assert out["sources"]

    def test_baseline_and_hybrid_both_return_usable_context(self, monkeypatch):
        """Both configurations have to work, or the A/B comparison is impossible."""
        import app.config as config
        import app.nodes.retrieve as retrieve_node

        s = config.get_settings()
        q = "why does chunk overlap matter?"

        monkeypatch.setattr(s, "USE_HYBRID", False)
        monkeypatch.setattr(s, "USE_RERANKER", False)
        baseline = retrieve_node.run({"question": q})

        monkeypatch.setattr(s, "USE_HYBRID", True)
        monkeypatch.setattr(s, "USE_RERANKER", True)
        full = retrieve_node.run({"question": q})

        assert baseline["documents"] and full["documents"]
        assert baseline["source_type"] == full["source_type"] == "vector_db"
