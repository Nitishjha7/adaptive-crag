"""Chroma similarity search wrapper.

Both the `retrieve` node and the ingestion script go through this, so k and any
threshold tuning live in one place instead of drifting apart in two.
"""

from typing import List, Optional, Tuple

from app.config import get_settings, get_vectorstore


def similarity_search(query: str, k: Optional[int] = None) -> List[str]:
    """Plain text of the top-k chunks.

    The node does not want Document objects: `CRAGState.documents` is a
    `List[str]` so web snippets and local chunks share one shape and `generate`
    never has to care which it got.
    """
    k = k or get_settings().TOP_K
    docs = get_vectorstore().similarity_search(query, k=k)
    return [d.page_content for d in docs]


def similarity_search_with_scores(query: str, k: Optional[int] = None):
    """For debugging and eval — (text, distance) pairs.

    Chroma returns cosine **distance** (0 = identical), not similarity.

    Not used on the production path. Relevance is decided by the LLM grader, not
    a score threshold — thresholds are corpus-specific and brittle.
    """
    k = k or get_settings().TOP_K
    return [
        (d.page_content, score)
        for d, score in get_vectorstore().similarity_search_with_score(query, k=k)
    ]


def similarity_search_with_sources(
    query: str, k: Optional[int] = None
) -> List[Tuple[str, str]]:
    """Top-k chunks as `(text, source)` pairs.

    `source` is the filename ingestion wrote into metadata
    (`ingest.py` -> `metadata={"source": path.name}`). That metadata was already
    being stored, just never read — citations need it.

    A separate function rather than a change to `similarity_search`, because
    that one is used by the eval and the tests, which only want text.
    """
    k = k or get_settings().TOP_K
    docs = get_vectorstore().similarity_search(query, k=k)
    return [(d.page_content, d.metadata.get("source", "unknown")) for d in docs]


def collection_count() -> int:
    """How many chunks are in the index — used to verify ingestion."""
    return get_vectorstore()._collection.count()
