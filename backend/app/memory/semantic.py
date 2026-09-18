"""Semantic memory: facts distilled from clusters of episodes.

Built on top of episodic memory, not independent of it - same relationship as
the sibling projects' semantic memory to their own episodic memory. An
episode is one data point ("this question, this verdict"); a semantic fact is
what several episodes clustering together by *meaning* (not exact match - see
episodic.py's use of vector similarity) collapse into, once there are enough
of them sharing the same failure to call it a pattern.

Deliberately not automatic - see the package docstring in
`app/memory/__init__.py`'s sibling modules for the same reasoning
self-healing-sql-agent's `consolidate_facts()` gives: this is a periodic,
explicitly-invoked job, not something every query should pay for.
"""

from __future__ import annotations

import logging

from app.memory.store import get_memory_store

log = logging.getLogger(__name__)

_MIN_CLUSTER_SIZE = 3
_CLUSTER_DISTANCE_THRESHOLD = 0.3

_FACTS_COLLECTION_SUFFIX = "_facts"


def _facts_store():
    """A second collection alongside the episodes one, same persisted directory.

    Kept separate from episodes rather than mixed metadata on the same
    collection, so `episodic.recall_similar`'s similarity search over
    questions never has to filter out fact documents that are not questions.
    """
    store = get_memory_store()
    if store is None:
        return None
    try:
        from langchain_chroma import Chroma

        from app.config import get_embeddings, get_settings

        settings = get_settings()
        return Chroma(
            collection_name="crag_memory_facts",
            embedding_function=get_embeddings(),
            persist_directory=settings.VECTORSTORE_DIR,
        )
    except Exception as exc:  # noqa: BLE001 - fail open
        log.warning("Facts store setup failed (%s)", exc)
        return None


def consolidate_facts() -> int:
    """Cluster ungrounded episodes by similarity, write one fact per cluster.

    A simple greedy clustering, not a full clustering algorithm: for each
    unclustered failed episode, gather every other failed episode within
    `_CLUSTER_DISTANCE_THRESHOLD` of it; if that group reaches
    `_MIN_CLUSTER_SIZE`, it becomes one fact. Good enough at the scale this
    memory actually holds (hundreds of episodes, not millions) - reaching for
    a real clustering library here would be solving a problem this project's
    scale does not have.
    """
    episode_store = get_memory_store()
    facts_store = _facts_store()
    if episode_store is None or facts_store is None:
        return 0

    try:
        collection = episode_store._collection
        raw = collection.get(where={"guardrail_passed": False}, include=["documents", "metadatas"])
        questions = raw.get("documents") or []
        if len(questions) < _MIN_CLUSTER_SIZE:
            return 0

        clustered = set()
        written = 0
        for i, question in enumerate(questions):
            if i in clustered:
                continue
            neighbors = episode_store.similarity_search_with_score(question, k=len(questions))
            cluster = [
                question
                for doc, distance in neighbors
                if distance <= _CLUSTER_DISTANCE_THRESHOLD and doc.page_content in questions
            ]
            if len(cluster) < _MIN_CLUSTER_SIZE:
                continue
            for j, other in enumerate(questions):
                if other in cluster:
                    clustered.add(j)
            fact = (
                f'Questions like "{question}" ({len(cluster)} similar cases) have '
                "repeatedly failed the groundedness check on this corpus - the "
                "retrieved context likely does not cover this topic well."
            )
            facts_store.add_texts(texts=[fact], metadatas=[{"cluster_size": len(cluster)}])
            written += 1
        return written
    except Exception as exc:  # noqa: BLE001 - fail open
        log.warning("consolidate_facts failed (%s)", exc)
        return 0


def recall_facts(question: str, limit: int = 3) -> list[str]:
    facts_store = _facts_store()
    if facts_store is None:
        return []
    try:
        results = facts_store.similarity_search_with_score(question, k=limit)
        return [doc.page_content for doc, distance in results if distance <= _CLUSTER_DISTANCE_THRESHOLD]
    except Exception as exc:  # noqa: BLE001 - fail open
        log.warning("recall_facts failed (%s)", exc)
        return []


def format_facts_for_prompt(facts: list[str]) -> str:
    if not facts:
        return ""
    return "Known pattern for this corpus:\n" + "\n".join(f"- {f}" for f in facts)
