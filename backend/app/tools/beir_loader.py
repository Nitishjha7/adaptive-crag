"""BEIR dataset loader — abhi SciFact.

**BEIR kyun, koi random HuggingFace dump kyun nahi:** BEIR retrieval benchmarks
ka standard suite hai, aur har dataset teen cheezein deta hai —

    corpus.jsonl    documents
    queries.jsonl   queries
    qrels/test.tsv  **relevance judgments** (kaunsa doc kis query ka jawab deta hai)

Teesri cheez asli value hai. `backend/data/` wale corpus me maine documents bhi
likhe aur eval labels bhi — RESULTS.md khud isko structural bias bolta hai. Yahan
labels dataset ke saath aate hain, kisi aur ne banaye hain.

**SciFact hi kyun:** ~5k abstracts — itne ki ranking sach me matter kare (22
chunks pe reranker ka A/B flat aaya tha, wahi limit thi), aur itne kam ki laptop
pe CPU embeddings me minute-do minute me ho jaye. TREC-COVID (171k) is machine pe
practical nahi.

**`datasets` library kyun nahi:** BEIR ki official zip seedha download ho jaati
hai aur format teen plain files hai. `datasets` pyarrow samet ek bada dependency
tree laata hai, sirf teen JSONL padhne ke liye.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple

from app.config import get_settings

BEIR_URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets"


def dataset_dir(name: str = "scifact") -> Path:
    return Path(get_settings().BEIR_DIR) / name


def ensure_downloaded(name: str = "scifact") -> Path:
    """Dataset local pe na ho to download + extract karo. Idempotent."""
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

    # Zip ke andar already `<name>/` folder hota hai, isliye parent me extract
    # karte hain — warna `beir/scifact/scifact/` ban jaata.
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        zf.extractall(target.parent)

    if not (target / "corpus.jsonl").exists():
        raise RuntimeError(f"[beir] extract ke baad corpus.jsonl nahi mila: {target}")

    print(f"[beir] ready at {target}", flush=True)
    return target


def load_corpus(name: str = "scifact", limit: int = 0) -> List[Tuple[str, str, str]]:
    """`(doc_id, title, text)` triples.

    **`limit` naive truncation nahi hai.** Pehle N documents lena eval ko tod
    deta: gold docs corpus me kahin bhi ho sakte hain, aur agar wo cut ho gaye
    to "local jaana chahiye" wale labels jhoothe ho jaate — system ke paas wo
    jawab hai hi nahi.

    Isliye limit lagne pe **pehle saare gold docs** (qrels se) rakhe jaate hain,
    phir baaki slots filler documents se bharte hain. Filler zaroori hai —
    unke bina retrieval trivial ho jaata, har doc kisi na kisi query ka jawab
    hota. Yahi tareeka chhote retrieval benchmarks banane ka standard hai.
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
    """`{query_id: [relevant doc_id, ...]}` — dataset ke apne relevance judgments.

    TSV format: `query-id  corpus-id  score`. Score 0 ka matlab "judged, par
    relevant nahi" hota hai, isliye wo drop kar dete hain — hume sirf wo queries
    chahiye jinka corpus me **sach me** jawab hai.
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
    """`{query_id: "SUPPORT" | "CONTRADICT"}` — dataset ka apna answer label.

    SciFact claim-verification dataset hai: har claim ke saath likha hai ki gold
    abstract usko **support karta hai ya contradict**. Ye `queries.jsonl` ke
    `metadata` me baitha hai, aur `load_queries` use drop kar deta hai kyunki
    routing ko uski zaroorat nahi.

    Answer quality naapne ke liye ye zaroori hai. Ab tak eval sirf ye naapta tha
    ki **route** sahi tha aur answer apne context se **grounded** tha. Ye dono
    is sawaal ka jawab nahi dete ki answer **sach me sahi hai ya nahi** — aur
    RESULTS.md khud likhta hai ki reranking ko *answer* pe asar dikhana chahiye,
    routing pe nahi. Wahi gap ye label bharta hai, aur wo bhi LLM-judge se nahi,
    dataset ki apni ground truth se.

    Ek query pe kai gold docs ho sakte hain. Agar unke labels **aapas me alag**
    hain to wo case skip ho jaata hai — mixed evidence pe "answer sahi tha ya
    nahi" ka koi imaandar jawab nahi hai.
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
