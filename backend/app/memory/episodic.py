"""Episodic memory: has a similar question been asked before, and how did it go.

Unlike the sibling projects' episodic memory (exact-signature match in
self-healing-sql-agent and code-guardian, since their unit is a SQL question
or an exact code shape), this one is genuine vector similarity - the unit
here is a natural-language question, which is exactly what embeddings are
for and exactly why this project already has an embedding model loaded.

One episode = one (question, verdict) pair. "Verdict" is `guardrail_passed`
straight from `CRAGState` - whether `validate_guardrails` found the answer
grounded - not a separate judgement invented for this feature.
"""

from __future__ import annotations

import logging
import time

from app.memory.store import get_memory_store

log = logging.getLogger(__name__)

_TOP_K = 3
# Chroma's cosine distance (0 = identical). Below this, two questions are
# considered "the same question asked again" rather than merely related -
# loose enough to catch a rephrasing, tight enough that two unrelated
# questions about the same corpus topic don't collide.
_SIMILARITY_DISTANCE_THRESHOLD = 0.25


def record_episode(question: str, source_type: str, guardrail_passed: bool) -> None:
    store = get_memory_store()
    if store is None:
        return
    try:
        store.add_texts(
            texts=[question],
            metadatas=[
                {
                    "source_type": source_type,
                    "guardrail_passed": bool(guardrail_passed),
                    "recorded_at": time.time(),
                }
            ],
        )
    except Exception as exc:  # noqa: BLE001 - fail open
        log.warning("record_episode failed (%s)", exc)


def record_episode_from_state(state: dict) -> None:
    """The one decision function - called once per query from build_graph.py.

    Skips a query that never reached a verdict at all (an error before
    `validate_guardrails` ran) rather than recording a misleading "passed".
    """
    if "guardrail_passed" not in state:
        return
    record_episode(
        question=state.get("question", ""),
        source_type=state.get("source_type", "unknown"),
        guardrail_passed=bool(state.get("guardrail_passed")),
    )


def recall_similar(question: str, limit: int = _TOP_K) -> list[dict]:
    """Past episodes for questions similar enough to count as precedent.

    Fail-open: any error, or no store, returns no episodes rather than
    raising into the query.
    """
    store = get_memory_store()
    if store is None:
        return []
    try:
        results = store.similarity_search_with_score(question, k=limit)
        return [
            {
                "question": doc.page_content,
                "guardrail_passed": doc.metadata.get("guardrail_passed"),
                "source_type": doc.metadata.get("source_type"),
                "distance": distance,
            }
            for doc, distance in results
            if distance <= _SIMILARITY_DISTANCE_THRESHOLD
        ]
    except Exception as exc:  # noqa: BLE001 - fail open
        log.warning("recall_similar failed (%s)", exc)
        return []


def format_episodes_for_prompt(episodes: list[dict]) -> str:
    if not episodes:
        return ""
    failed = sum(1 for e in episodes if e.get("guardrail_passed") is False)
    if failed == 0:
        return ""
    return (
        f"Note: {failed} of {len(episodes)} similar past question(s) on this "
        "corpus previously failed the groundedness check - answer carefully "
        "and prefer citing the retrieved context explicitly."
    )
