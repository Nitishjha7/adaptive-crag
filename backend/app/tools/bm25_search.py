"""BM25 keyword search over the same corpus Chroma holds.

**Ye kyun, jab vector search already hai:** dono alag cheezon me strong hain.

Vector search *meaning* pakadta hai — "annual time off" aur "paid leave
entitlement" paas aa jaate hain chahe ek bhi word common na ho. Lekin exact
tokens pe wo surprisingly kamzor hai: `EMP-4582` aur `EMP-4583` embedding space
me lagbhag ek hi jagah baithte hain, kyunki unka *matlab* same hai.

BM25 ulta hai — wo exact term match pe chalta hai, IDF se rare terms ko zyada
weight deta hai. Isliye identifiers, product codes, version numbers, aur proper
nouns pe wo jeetta hai.

Production RAG dono chalata hai aur results fuse karta hai. Yahi `web_search.py`
wala pattern hai — ek interface, do implementations.

**Is corpus pe iska fayda seemit hai** aur ye maan lena zaroori hai: 7 concept
documents me koi SKU ya employee ID nahi hai. BM25 yahan mostly wahi chunks
laayega jo vector search laata hai. Isliye ye `USE_HYBRID` flag ke peeche hai aur
eval se measure hota hai, assume nahi kiya jaata.
"""

import re
from functools import lru_cache
from typing import List, Optional, Tuple

from app.config import get_settings, get_vectorstore

# Simple tokenizer: lowercase + alphanumeric runs. Stemming jaan-boojh ke nahi —
# ek aur dependency (nltk/snowball) ka fayda 22 chunks pe measure hi nahi hoga,
# aur ye project har addition ko measure karne ke usool pe chalta hai.
_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> List[str]:
    return _TOKEN.findall(text.lower())


@lru_cache
def _build_index():
    """Poore corpus ko memory me load karke BM25 index banao.

    **Poora corpus kyun:** BM25 ka IDF term ki *corpus-wide* frequency pe depend
    karta hai. Sirf top-k chunks pe BM25 chalane ka koi matlab nahi — IDF galat
    hoga aur scores bekaar.

    22 chunks pe ye trivial hai. Bade corpus pe ye approach nahi chalti; wahan
    ek proper inverted index (Elasticsearch / OpenSearch / Tantivy) chahiye.
    Ye limitation asli hai aur docs me likhi hui hai.

    `lru_cache` isliye ki index ek baar bane. Ingestion ke baad ise clear karna
    padta hai — `bust_cache()` dekh.
    """
    from rank_bm25 import BM25Okapi

    store = get_vectorstore()
    # `include` me "documents" aur "metadatas" — embeddings nahi chahiye, wo
    # bade hote hain aur BM25 ko unse koi kaam nahi.
    raw = store._collection.get(include=["documents", "metadatas"])

    texts = raw.get("documents") or []
    metas = raw.get("metadatas") or [{}] * len(texts)
    sources = [(m or {}).get("source", "unknown") for m in metas]

    if not texts:
        return None, [], []

    return BM25Okapi([tokenize(t) for t in texts]), texts, sources


def bust_cache() -> None:
    """Ingestion ke baad index stale ho jaata hai. Tests aur ingest isse clear karte hain."""
    _build_index.cache_clear()


def bm25_search(query: str, k: Optional[int] = None) -> List[Tuple[str, str]]:
    """Top-k `(text, source)` pairs, BM25 score ke hisaab se.

    Corpus khaali ho to khaali list — exception nahi. Hybrid retrieval me BM25
    ek *additional* signal hai; uska fail hona poori retrieval nahi girana chahiye.
    """
    k = k or get_settings().TOP_K
    index, texts, sources = _build_index()
    if index is None:
        return []

    scores = index.get_scores(tokenize(query))

    # Zero-score chunks drop kar dete hain: BM25 me 0 ka matlab hai query ka koi
    # bhi term us chunk me nahi hai. Unhe rank karna fusion me shor bharta hai.
    ranked = sorted(
        (i for i, s in enumerate(scores) if s > 0),
        key=lambda i: scores[i],
        reverse=True,
    )[:k]

    return [(texts[i], sources[i]) for i in ranked]
