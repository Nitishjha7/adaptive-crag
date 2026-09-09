"""Hybrid retrieval + reranking (Phase 9).

Ye tests **structure** check karte hain, ranking quality nahi. "Reranker behtar
chunks laata hai" ek measurement claim hai — wo eval ka kaam hai
(`eval/RESULTS.md`), unit test ka nahi. Yahan sirf ye dekha jaata hai ki fusion
ka math sahi hai, flags sach me kaam karte hain, aur failure path graceful hai.
"""

import pytest

from app.tools.bm25_search import bm25_search, tokenize
from app.tools.reranker import reciprocal_rank_fusion, rerank


class TestTokenizer:
    def test_lowercases_and_splits(self):
        assert tokenize("Chunk OVERLAP matters!") == ["chunk", "overlap", "matters"]

    def test_keeps_alphanumerics_together(self):
        """Identifiers ek token rehne chahiye — yahi wo case hai jahan BM25
        vector search se behtar hai."""
        assert "bge" in tokenize("BAAI/bge-small-en-v1.5")
        assert "v1" in tokenize("BAAI/bge-small-en-v1.5")


class TestBM25:
    def test_finds_the_right_doc_by_keyword(self):
        hits = bm25_search("chunk overlap", k=3)
        assert hits, "BM25 ne kuch nahi diya"
        assert any("chunking" in source for _, source in hits)

    def test_returns_text_source_pairs(self):
        """Shape vector search jaisi honi chahiye, warna fusion me mix nahi kar sakte."""
        for item in bm25_search("embeddings", k=2):
            assert isinstance(item, tuple) and len(item) == 2
            assert all(isinstance(x, str) for x in item)

    def test_nonsense_query_returns_nothing_not_garbage(self):
        """BM25 me score 0 ka matlab hai koi term match nahi hua. Aise chunks
        rank karna fusion me sirf shor daalta hai, isliye wo drop hote hain."""
        assert bm25_search("zzzzqqqq xkcdplover", k=4) == []


class TestRRF:
    def test_document_in_both_lists_ranks_above_one_in_either(self):
        """RRF ka poora point yahi hai — dono retrievers jispe agree karte hain
        wo upar aata hai."""
        a = [("both", "s"), ("only_a", "s")]
        b = [("only_b", "s"), ("both", "s")]

        fused = [text for text, _ in reciprocal_rank_fusion([a, b])]

        assert fused[0] == "both", fused

    def test_dedupes_across_lists(self):
        a = [("x", "s"), ("y", "s")]
        b = [("x", "s")]
        assert [t for t, _ in reciprocal_rank_fusion([a, b])] == ["x", "y"]

    def test_ignores_score_scale_entirely(self):
        """Ye wo property hai jiski wajah se RRF chuna gaya: vector distance
        (chhota = behtar) aur BM25 score (bada = behtar) ko normalize kiye bina
        merge karna. RRF sirf rank padhta hai, isliye scale matter hi nahi karta."""
        one = [("a", "s"), ("b", "s")]
        # Same ranking, koi score kahin hai hi nahi — result identical hona chahiye
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
        """Reranking ek improvement hai, requirement nahi. Model load fail ho
        jaye to retrieval chalti rehni chahiye — bas thodi kam accurate."""
        import app.tools.reranker as mod

        def _boom():
            raise RuntimeError("model download failed")

        monkeypatch.setattr(mod, "get_cross_encoder", _boom)

        candidates = [("first", "a.md"), ("second", "b.md"), ("third", "c.md")]
        assert rerank("q", candidates, k=2) == candidates[:2]


class TestRetrieveNodeFlags:
    """Flags sach me pipeline badalte hain — ye zaroori hai kyunki eval inhi se
    baseline vs hybrid+rerank compare karta hai."""

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
        """Dono configurations kaam karni chahiye — warna A/B comparison hi
        impossible hai."""
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
