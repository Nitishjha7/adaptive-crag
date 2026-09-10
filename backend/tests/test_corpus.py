"""Multi-corpus support — collection isolation aur BEIR subset logic.

Ye tests **network hit nahi karte**. BEIR download ek 5k-abstract zip hai; usko
har test run me kheenchna slow bhi hai aur flaky bhi. Jo cheez yahan test karni
hai wo download nahi, **logic** hai: kya sahi collection chunni jaati hai, aur
kya subset lene pe gold docs bachte hain.
"""

import json

import pytest


class TestCollectionIsolation:
    """Dono corpora alag Chroma collections me rehne chahiye.

    Ye cosmetic nahi hai: mix ho gaye to SciFact ke 17k chunks concepts wale 22
    chunks ke saath retrieval me aa jaate, aur **dono ke eval numbers bekaar**
    ho jaate.
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
    """`limit` gold docs ko drop nahi karna chahiye.

    Naive truncation (pehle N documents) eval ko chupke se tod deta hai: gold
    doc cut ho gaya to "local jaana chahiye" label jhootha ho jaata, kyunki
    system ke paas wo jawab hai hi nahi. Wo failure eval me **grader ki galti**
    jaisa dikhta, jabki galti corpus ki hoti.
    """

    @pytest.fixture
    def fake_beir(self, tmp_path, monkeypatch):
        """Chhota fake BEIR dataset — koi download nahi."""
        import app.tools.beir_loader as loader

        root = tmp_path / "scifact"
        (root / "qrels").mkdir(parents=True)

        # 10 docs; gold wale jaan-boojh ke *aakhir me* rakhe hain, taaki naive
        # truncation unhe kaate aur test us bug ko pakde.
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

        assert "d8" in ids, "gold doc subset se gir gaya -- eval labels jhoothe ho jayenge"
        assert len(ids) == 3

    def test_subset_still_includes_filler(self, fake_beir):
        """Sirf gold docs ingest karna retrieval ko trivial bana deta -- har
        document kisi na kisi query ka jawab hota."""
        ids = [d for d, _, _ in fake_beir.load_corpus("scifact", limit=4)]
        assert any(d not in {"d8"} for d in ids)

    def test_no_limit_returns_everything(self, fake_beir):
        assert len(fake_beir.load_corpus("scifact")) == 10

    def test_qrels_drop_zero_scored_judgements(self, fake_beir):
        """Score 0 ka matlab "judged, par relevant nahi" hota hai. Usko gold
        maan lena eval ko silently galat kar dega."""
        qrels = fake_beir.load_qrels("scifact", "test")

        assert qrels["q1"] == ["d8"], qrels
        assert "d9" not in qrels["q1"]
