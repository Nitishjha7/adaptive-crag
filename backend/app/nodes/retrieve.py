"""`retrieve` node — context from the local knowledge base.

The graph's entry point. **No relevance decision happens here.** Similarity
search always returns k results whether or not anything relevant exists, which
is naive RAG's core failure mode. Judging them is the next node's job.

    vector search  ─┐
                    ├─ RRF fusion ─→ rerank ─→ top-k
    BM25 search    ─┘

Both stages sit behind flags (`USE_HYBRID`, `USE_RERANKER`). Not for
configurability — so the eval can turn them off and compare against a baseline.
In this project a feature is not a feature until its benefit can be shown.
"""

from typing import List, Tuple

from app.config import get_settings
from app.schemas.crag_state import CRAGState
from app.tools.vector_search import similarity_search_with_sources


def _gather_candidates(question: str, settings) -> Tuple[List[Tuple[str, str]], List[str]]:
    """Gather candidates. Returns `(pairs, log_parts)`."""
    # The reranker needs more than TOP_K to choose from, or it is a no-op.
    n = settings.RETRIEVAL_CANDIDATES if settings.USE_RERANKER else settings.TOP_K

    vector_hits = similarity_search_with_sources(question, k=n)
    log_parts = [f"vector={len(vector_hits)}"]

    if not settings.USE_HYBRID:
        return vector_hits, log_parts

    from app.tools.bm25_search import bm25_search
    from app.tools.reranker import reciprocal_rank_fusion

    bm25_hits = bm25_search(question, k=n)
    log_parts.append(f"bm25={len(bm25_hits)}")

    # BM25 found nothing (no query term appears in the corpus), so there is
    # nothing to fuse — an empty list contributes nothing to RRF.
    if not bm25_hits:
        return vector_hits, log_parts

    fused = reciprocal_rank_fusion([vector_hits, bm25_hits])
    log_parts.append(f"fused={len(fused)}")
    return fused, log_parts


def run(state: CRAGState) -> dict:
    question = state["question"]
    s = get_settings()

    candidates, log_parts = _gather_candidates(question, s)

    if s.USE_RERANKER and len(candidates) > 1:
        from app.tools.reranker import rerank

        before = len(candidates)
        candidates = rerank(question, candidates, k=s.TOP_K)
        log_parts.append(f"reranked {before}->{len(candidates)}")
    else:
        candidates = candidates[: s.TOP_K]

    documents = [text for text, _ in candidates]
    # Dedupe while keeping order — four chunks often come from two files, and
    # the first source belongs to the most relevant chunk.
    sources = list(dict.fromkeys(source for _, source in candidates))

    return {
        "documents": documents,
        "sources": sources,
        "source_type": "vector_db",
        "logs": [f"retrieve -> {len(documents)} chunks ({', '.join(log_parts)})"],
    }
