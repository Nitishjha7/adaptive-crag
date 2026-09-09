"""Cross-encoder reranking.

**Retriever aur reranker ka asli farak** (ye interview me poochha jaata hai):

- Retriever ek **bi-encoder** hai — query aur document ko *alag-alag* embed karta
  hai. Isliye fast: document vectors pehle se bane hote hain, query time pe sirf
  ek embedding aur ek nearest-neighbour lookup. Lekin query aur document ke beech
  ka interaction wo dekh hi nahi sakta, kyunki dono kabhi ek saath model me
  jaate hi nahi.
- Reranker ek **cross-encoder** hai — query aur document ko *ek saath* model me
  daalta hai. Model dono ko ek doosre ke context me padhta hai, isliye kaafi
  zyada accurate. Keemat: har (query, document) pair pe ek forward pass. Poore
  corpus pe chalana namumkin hai.

Isiliye ye do-step design hai: **sasta retriever candidates laata hai, mehnga
reranker unme se best chunta hai.**

**Is project me reranker ka point answer quality nahi hai — grader ka input hai.**
`grade_documents` decide karta hai ki local context kaafi hai ya nahi. Agar
retrieval sahi chunk laayi par wo top-k me neeche reh gaya, grader use dekh hi
nahi paata aur galat "no" de sakta hai. Reranker sahi chunk ko upar laata hai,
yaani grader ko behtar input milta hai.

Model: `Xenova/ms-marco-MiniLM-L-6-v2` — 80MB ONNX, local, koi API key nahi.
Wahi stance jo embeddings ka hai.
"""

from functools import lru_cache
from typing import List, Optional, Tuple

from app.config import get_settings


@lru_cache
def get_cross_encoder():
    """Reranker model. Pehli baar ~80MB download; Docker build me pre-cached hai."""
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(model_name=get_settings().RERANKER_MODEL)


def rerank(
    query: str, candidates: List[Tuple[str, str]], k: Optional[int] = None
) -> List[Tuple[str, str]]:
    """`(text, source)` candidates ko query ke hisaab se dobara rank karke top-k do.

    Failure pe original order lauta dete hain, exception nahi — reranking ek
    *improvement* hai, requirement nahi. Model load fail ho jaye to retrieval
    phir bhi kaam karni chahiye, bas thodi kam accurate.
    """
    k = k or get_settings().TOP_K
    if not candidates:
        return []
    if len(candidates) <= 1:
        return candidates[:k]

    try:
        scores = list(get_cross_encoder().rerank(query, [text for text, _ in candidates]))
    except Exception:  # noqa: BLE001 — neeche wali docstring dekh
        return candidates[:k]

    order = sorted(range(len(candidates)), key=lambda i: scores[i], reverse=True)
    return [candidates[i] for i in order[:k]]


def reciprocal_rank_fusion(
    rankings: List[List[Tuple[str, str]]], k_rrf: int = 60
) -> List[Tuple[str, str]]:
    """Kai ranked lists ko ek me merge karo — Reciprocal Rank Fusion.

    `score(d) = sum over lists of 1 / (k_rrf + rank(d))`

    **Score normalization kyun nahi:** vector search cosine *distance* deta hai
    (0 = best) aur BM25 ek unbounded positive score (bada = best). Ye alag
    scales hain, aur unhe ek dusre me convert karna corpus-specific tuning
    maangta — jo brittle hota hai.

    RRF sirf **rank** dekhta hai, score nahi. Isliye dono lists ka scale
    bilkul irrelevant ho jaata hai. Isi wajah se ye hybrid search ka default
    fusion hai.

    `k_rrf=60` standard value hai (original RRF paper). Ye top ranks ka asar
    thoda dabata hai taaki ek list akeli poora result set na chura le.
    """
    scores: dict = {}
    keep: dict = {}

    for ranking in rankings:
        for rank, (text, source) in enumerate(ranking):
            scores[text] = scores.get(text, 0.0) + 1.0 / (k_rrf + rank + 1)
            keep.setdefault(text, source)

    ordered = sorted(scores, key=lambda t: scores[t], reverse=True)
    return [(text, keep[text]) for text in ordered]
