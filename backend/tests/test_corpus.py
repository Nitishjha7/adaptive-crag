"""Multi-corpus support — collection isolation and the BEIR subset logic.

These tests **do not touch the network**. The BEIR download is a 5k-abstract zip;
pulling it on every test run would be both slow and flaky. What needs testing is
not the download but the **logic**: is the right collection chosen, and do the
gold documents survive a subset?
"""

import json

import pytest


class TestCollectionIsolation:
    """The two corpora must live in separate Chroma collections.

    Not cosmetic: if they mixed, SciFact's 17k chunks would surface alongside the
    22 concepts chunks in retrieval and **both sets of eval numbers would be
    worthless**.
    """

    def test_concepts_and_scifact_get_different_collections(self):
        from app.config import Settings

        concepts = Settings(CORPUS="concepts").collection_name
        scifact = Settings(CORPUS="scifact").collection_name

        assert concepts != scifact
        assert concepts == "crag_docs", "purani collection ka naam badalna index tod dega"

    def test_collection_name_follows_corpus(self):
        from app.config import Settings

        assert Settings(CORPUS="scifact").collection_name == "crag_scifact"


class TestBeirSubset:
    """`limit` must not drop gold documents.

    Naive truncation (the first N documents) breaks the eval silently: if a gold
    document is cut, its "should stay local" label becomes false, because the
    system does not have that answer. In the eval that failure looks like **the
    grader being wrong** when the corpus was wrong.
    """

    @pytest.fixture
    def fake_beir(self, tmp_path, monkeypatch):
        """A tiny fake BEIR dataset — no download."""
        import app.tools.beir_loader as loader

        root = tmp_path / "scifact"
        (root / "qrels").mkdir(parents=True)

        # 10 docs; the gold ones are deliberately placed *at the end*, so a
        # naive truncation would cut them and the test would catch that bug.
        with (root / "corpus.jsonl").open("w", encoding="utf-8") as fh:
            for i in range(10):
                fh.write(json.dumps({
                    "_id": f"d{i}", "title": f"T{i}", "text": f"body {i}"
                }) + "\n")

        with (root / "queries.jsonl").open("w", encoding="utf-8") as fh:
            fh.write(json.dumps({"_id": "q1", "text": "claim one"}) + "\n")

        (root / "qrels" / "test.tsv").write_text(
            "query-id\tcorpus-id\tscore\nq1\td8\t1\nq1\td9\t0\n", encoding="utf-8"
        )

        monkeypatch.setattr(loader, "ensure_downloaded", lambda name="scifact": root)
        return loader

    def test_subset_keeps_gold_docs(self, fake_beir):
        ids = [d for d, _, _ in fake_beir.load_corpus("scifact", limit=3)]

        assert "d8" in ids, "gold doc dropped from the subset - the eval labels would be lies"
        assert len(ids) == 3

    def test_subset_still_includes_filler(self, fake_beir):
        """Ingesting only gold documents would make retrieval trivial -- every
        document would answer some query."""
        ids = [d for d, _, _ in fake_beir.load_corpus("scifact", limit=4)]
        assert any(d not in {"d8"} for d in ids)

    def test_no_limit_returns_everything(self, fake_beir):
        assert len(fake_beir.load_corpus("scifact")) == 10

    def test_qrels_drop_zero_scored_judgements(self, fake_beir):
        """A score of 0 means "judged, but not relevant". Treating it as gold
        would make the eval silently wrong."""
        qrels = fake_beir.load_qrels("scifact", "test")

        assert qrels["q1"] == ["d8"], qrels
        assert "d9" not in qrels["q1"]


class TestCorpusNameValidation:
    """A corpus name reaches Chroma as a collection name.

    `collection_for` used to interpolate the raw value into `f"crag_{corpus}"`,
    so a request carrying `../../etc` produced a Chroma
    `InvalidArgumentError` that nothing caught - a 500 on a request the client
    got wrong. The upload branch never had this problem because it sanitises
    through `session_collection`.
    """

    def test_a_valid_corpus_still_maps_to_its_collection(self):
        from app.config import collection_for

        assert collection_for("concepts") == "crag_docs"
        assert collection_for("scifact") == "crag_scifact"

    def test_a_path_like_corpus_is_refused(self):
        import pytest

        from app.config import collection_for

        with pytest.raises(ValueError):
            collection_for("../../etc")

    def test_the_api_answers_400_not_500(self, client):
        """The GET endpoints take `corpus` as a query parameter, so Pydantic's
        pattern on `QueryIn` does not cover them. The ValueError handler does."""
        response = client.get("/api/documents?corpus=../../etc")
        assert response.status_code == 400

    def test_the_query_body_rejects_it_as_a_validation_error(self, client):
        """On `/api/query` the pattern on `QueryIn` catches it first, which is a
        422 - the same class of answer, raised one layer earlier."""
        response = client.post(
            "/api/query", json={"question": "anything", "corpus": "../../etc"}
        )
        assert response.status_code == 422
