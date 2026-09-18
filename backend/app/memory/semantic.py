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
            # Embed the cluster's representative *question*, not the fact's own
            # prose - recall_facts searches by an incoming question, and a
            # declarative sentence like the fact text above sits much further
            # in embedding space from a question than another question does.
            # The fact text itself travels in metadata, read back verbatim.
            facts_store.add_texts(
                texts=[question], metadatas=[{"fact": fact, "cluster_size": len(cluster)}]
            )
            written += 1
        if written:
            _clear_chroma_client_cache()
        return written
    except Exception as exc:  # noqa: BLE001 - fail open
        log.warning("consolidate_facts failed (%s)", exc)
        return 0


def _clear_chroma_client_cache() -> None:
    """Force the next `_facts_store()`/`get_memory_store()` call to open a
    fresh client for this path.

    Chroma's `PersistentClient` is cached process-wide, keyed by persist
    directory (`chromadb.api.client.SharedSystemClient._identifier_to_system`)
    - not something this module opted into, and not documented anywhere
    obvious. Caught live: writing a fact via `POST /api/memory/consolidate`
    and then querying from the *same running process* returned no fact,
    while a fresh `python -c` process against the same directory saw it
    immediately. Without this, "run consolidation, then ask a question" would
    silently not work until the process restarted - exactly the kind of gap
    that looks fine in every unit test (each test process is fresh) and only
    shows up against a long-running server.
    """
    try:
        from chromadb.api.client import SharedSystemClient

        SharedSystemClient.clear_system_cache()
    except Exception as exc:  # noqa: BLE001 - fail open; worst case is the old staleness, not a crash
        log.warning("Could not clear Chroma client cache (%s)", exc)


def recall_facts(question: str, limit: int = 3) -> list[str]:
    facts_store = _facts_store()
    if facts_store is None:
        return []
    try:
        results = facts_store.similarity_search_with_score(question, k=limit)
        return [
            doc.metadata["fact"]
            for doc, distance in results
            if distance <= _CLUSTER_DISTANCE_THRESHOLD
        ]
    except Exception as exc:  # noqa: BLE001 - fail open
        log.warning("recall_facts failed (%s)", exc)
        return []


def format_facts_for_prompt(facts: list[str]) -> str:
    if not facts:
        return ""
    return "Known pattern for this corpus:\n" + "\n".join(f"- {f}" for f in facts)
