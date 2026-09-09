"""`retrieve` node — local knowledge base se context.

Graph ka entry point. Yahan **koi relevance ka faisla nahi hota** — similarity
search hamesha k results deta hai, chahe corpus me kuch relevant ho ya na ho.
Wahi naive RAG ka core failure mode hai; uska faisla agla node
(`grade_documents`) karta hai.

Pipeline (Phase 9 ke baad):

    vector search  ─┐
                    ├─ RRF fusion ─→ rerank ─→ top-k
    BM25 search    ─┘

Dono stages flags ke peeche hain (`USE_HYBRID`, `USE_RERANKER`). Ye sirf
configurability ke liye nahi hai — ye isliye hai taaki eval dono ko off karke
baseline se compare kar sake. Is project me ek feature tab tak feature nahi hai
jab tak uska fayda dikhaya na ja sake.
"""

from typing import List, Tuple

from app.config import get_settings
from app.schemas.crag_state import CRAGState
from app.tools.vector_search import similarity_search_with_sources


def _gather_candidates(question: str, settings) -> Tuple[List[Tuple[str, str]], List[str]]:
    """Candidates ikattha karo. `(pairs, log_parts)` lautata hai."""
    # Reranker ko chunne ke liye TOP_K se zyada chahiye, warna wo no-op hai.
    n = settings.RETRIEVAL_CANDIDATES if settings.USE_RERANKER else settings.TOP_K

    vector_hits = similarity_search_with_sources(question, k=n)
    log_parts = [f"vector={len(vector_hits)}"]

    if not settings.USE_HYBRID:
        return vector_hits, log_parts

    from app.tools.bm25_search import bm25_search
    from app.tools.reranker import reciprocal_rank_fusion

    bm25_hits = bm25_search(question, k=n)
    log_parts.append(f"bm25={len(bm25_hits)}")

    # BM25 ne kuch nahi diya (query ka koi term corpus me nahi) to fuse karne ka
    # matlab nahi — ek khaali list RRF me kuch add nahi karti.
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
    # Order rakh ke dedupe — 4 chunks aksar 2 hi files se aate hain, aur pehla
    # source sabse relevant chunk ka hai.
    sources = list(dict.fromkeys(source for _, source in candidates))

    return {
        "documents": documents,
        "sources": sources,
        "source_type": "vector_db",
        "logs": [f"retrieve -> {len(documents)} chunks ({', '.join(log_parts)})"],
    }
