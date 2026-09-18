"""BEIR dataset loader — SciFact for now.

**Why BEIR rather than some HuggingFace dump:** BEIR is the standard suite for
retrieval benchmarks, and every dataset in it ships three things —

    corpus.jsonl    documents
    queries.jsonl   queries
    qrels/test.tsv  **relevance judgments** (which document answers which query)

The third is the real value. In `backend/data/` I wrote both the documents and
the eval labels, which RESULTS.md calls out as structural bias. Here the labels
come with the dataset; somebody else made them.

**Why SciFact specifically:** ~5k abstracts — enough that ranking actually
matters (the reranker A/B came out flat on 22 chunks, which was the limit), and
few enough to embed on a laptop CPU in a couple of minutes. TREC-COVID (171k) is
not practical on this machine.

**Why not the `datasets` library:** BEIR's official zip downloads directly and
the format is three plain files. `datasets` drags in a large dependency tree,
pyarrow included, to read three JSONL files.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple

from app.config import get_settings

BEIR_URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets"


def dataset_dir(name: str = "scifact") -> Path:
    return Path(get_settings().BEIR_DIR) / name


def ensure_downloaded(name: str = "scifact") -> Path:
    """Download and extract the dataset if it isn't present locally. Idempotent."""
    import io
    import urllib.request
    import zipfile

    target = dataset_dir(name)
    if (target / "corpus.jsonl").exists():
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    url = f"{BEIR_URL}/{name}.zip"
    print(f"[beir] downloading {url} ...", flush=True)

    with urllib.request.urlopen(url, timeout=300) as resp:
        blob = resp.read()

    # The zip already contains a `<name>/` folder, so extract into the parent —
    # otherwise it becomes `beir/scifact/scifact/`.
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        zf.extractall(target.parent)

    if not (target / "corpus.jsonl").exists():
        raise RuntimeError(f"[beir] corpus.jsonl missing after extract: {target}")

    print(f"[beir] ready at {target}", flush=True)
    return target


def load_corpus(name: str = "scifact", limit: int = 0) -> List[Tuple[str, str, str]]:
    """`(doc_id, title, text)` triples.

    **`limit` is not naive truncation.** Taking the first N documents would
    break the eval: gold documents sit anywhere in the file, and any that got cut
    would leave a "should stay local" label that is simply false — the system
    does not have that answer.

    So when a limit applies, **every gold document** (from qrels) is kept first
    and the remaining slots are filled with non-gold documents. The filler
    matters: without it every indexed document would answer some query and
    retrieval would be trivially easy. This is the standard way to build a small
    retrieval benchmark.
    """
    path = ensure_downloaded(name) / "corpus.jsonl"

    if not limit:
        out = []
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                out.append((row["_id"], row.get("title", ""), row.get("text", "")))
        return out

    gold_ids = {d for docs in load_qrels(name, "test").values() for d in docs}

    kept, filler = [], []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            item = (row["_id"], row.get("title", ""), row.get("text", ""))
            (kept if row["_id"] in gold_ids else filler).append(item)

    remaining = max(0, limit - len(kept))
    return kept + filler[:remaining]


def load_queries(name: str = "scifact") -> Dict[str, str]:
    """`{query_id: query_text}`."""
    path = ensure_downloaded(name) / "queries.jsonl"
    with path.open(encoding="utf-8") as fh:
        return {row["_id"]: row["text"] for row in map(json.loads, fh)}


def load_qrels(name: str = "scifact", split: str = "test") -> Dict[str, List[str]]:
    """`{query_id: [relevant doc_id, ...]}` — the dataset's own relevance judgments.

    TSV format: `query-id  corpus-id  score`. A score of 0 means "judged, but not
    relevant", so those are dropped — only queries whose answer is **actually** in
    the corpus are useful here.
    """
    path = ensure_downloaded(name) / "qrels" / f"{split}.tsv"
    out: Dict[str, List[str]] = {}
    with path.open(encoding="utf-8") as fh:
        next(fh, None)  # header
        for line in fh:
            parts = line.strip().split("\t")
            if len(parts) < 3:
                continue
            qid, did, score = parts[0], parts[1], parts[2]
            if float(score) > 0:
                out.setdefault(qid, []).append(did)
    return out


def load_query_verdicts(name: str = "scifact") -> Dict[str, str]:
    """`{query_id: "SUPPORT" | "CONTRADICT"}` — the dataset's own answer label.

    SciFact is a claim-verification dataset: each claim records whether the gold
    abstract **supports or contradicts** it. That sits in `queries.jsonl` under
    `metadata`, and `load_queries` drops it because routing has no use for it.

    Measuring answer quality does need it. Until this existed the eval only asked
    whether the **route** was right and whether the answer was **grounded** in its
    context. Neither answers whether the answer was **actually correct** — and
    RESULTS.md says plainly that reranking should show up in the *answer*, not in
    routing. This label fills that gap, and does it with the dataset's own ground
    truth rather than an LLM judge.

    A query can have several gold documents. If their labels **disagree**, the
    case is skipped — on mixed evidence there is no honest answer to score
    against.
    """
    path = ensure_downloaded(name) / "queries.jsonl"
    out: Dict[str, str] = {}
    with path.open(encoding="utf-8") as fh:
        for row in map(json.loads, fh):
            meta = row.get("metadata") or {}
            labels = {
                item.get("label")
                for items in meta.values()
                for item in (items or [])
                if item.get("label")
            }
            if len(labels) == 1:
                out[row["_id"]] = labels.pop()
    return out
