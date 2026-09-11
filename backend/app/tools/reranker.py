"""Cross-encoder reranking.

**The real difference between a retriever and a reranker** (a common interview
question):

- A retriever is a **bi-encoder** — it embeds the query and the document
  *separately*. That is why it is fast: document vectors are precomputed, and
  query time costs one embedding plus a nearest-neighbour lookup. It also means
  it cannot see any interaction between query and document, because the two never
  enter the model together.
- A reranker is a **cross-encoder** — it puts query and document through the
  model *together*, so the model reads each in the context of the other. Much
  more accurate, at the cost of one forward pass per (query, document) pair,
  which makes running it over a whole corpus impossible.

Hence the two-step design: **a cheap retriever fetches candidates, an expensive
reranker picks the best of them.**

**In this project the reranker is aimed at the grader's input, not at answer
quality.** `grade_documents` decides whether the local context is sufficient. If
retrieval found the right chunk but left it below the top-k cut, the grader never
sees it and can return a wrong "no". The reranker pulls that chunk up.

Model: `Xenova/ms-marco-MiniLM-L-6-v2` — 80 MB ONNX, local, no API key. Same
stance as the embeddings.
"""

from functools import lru_cache
from typing import List, Optional, Tuple

from app.config import get_settings


@lru_cache
def get_cross_encoder():
    """The reranker model. ~80 MB on first download; pre-cached in the image."""
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(model_name=get_settings().RERANKER_MODEL)


def rerank(
    query: str, candidates: List[Tuple[str, str]], k: Optional[int] = None
) -> List[Tuple[str, str]]:
    """Re-rank `(text, source)` candidates against the query and return top-k.

    On failure it returns the original order rather than raising: reranking is an
    *improvement*, not a requirement. If the model fails to load, retrieval should
    still work — just a little less accurately.
    """
    k = k or get_settings().TOP_K
    if not candidates:
        return []
    if len(candidates) <= 1:
        return candidates[:k]

    try:
        scores = list(get_cross_encoder().rerank(query, [text for text, _ in candidates]))
    except Exception:  # noqa: BLE001 — see the docstring above
        return candidates[:k]

    order = sorted(range(len(candidates)), key=lambda i: scores[i], reverse=True)
    return [candidates[i] for i in order[:k]]


def reciprocal_rank_fusion(
    rankings: List[List[Tuple[str, str]]], k_rrf: int = 60
) -> List[Tuple[str, str]]:
    """Merge several ranked lists into one — Reciprocal Rank Fusion.

    `score(d) = sum over lists of 1 / (k_rrf + rank(d))`

    **Why no score normalisation:** vector search returns cosine *distance*
    (0 = best) and BM25 returns an unbounded positive score (higher = best).
    Different scales, and converting one into the other needs corpus-specific
    tuning, which is brittle.

    RRF looks only at **rank**, never at score, so the scale of either list stops
    mattering. That is why it is the default fusion for hybrid search.

    `k_rrf=60` is the value from the original RRF paper. It damps the influence of
    the very top ranks so one list cannot run away with the whole result set.
    """
    scores: dict = {}
    keep: dict = {}

    for ranking in rankings:
        for rank, (text, source) in enumerate(ranking):
            scores[text] = scores.get(text, 0.0) + 1.0 / (k_rrf + rank + 1)
            keep.setdefault(text, source)

    ordered = sorted(scores, key=lambda t: scores[t], reverse=True)
    return [(text, keep[text]) for text in ordered]
