"""Lazy, fail-open handle to the memory collection.

A second Chroma collection in the same persisted directory the retrieval
corpus already uses (`app/config.py`'s `VECTORSTORE_DIR`) - separate from
`crag_docs`/`crag_scifact` so a stored episode can never leak into retrieval
results, the same reasoning `config.py`'s `collection_name` property already
gives for keeping the two corpora apart.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

log = logging.getLogger(__name__)

_MEMORY_COLLECTION = "crag_memory_episodes"


@lru_cache
def get_memory_store():
    """Return the memory Chroma collection, or None if memory is unavailable.

    Cached like every other client factory in `app/config.py` - one instance
    per process, not reopened per request.
    """
    if os.environ.get("DISABLE_MEMORY_STORE", "").lower() in ("1", "true", "yes"):
        log.info("Memory store disabled by DISABLE_MEMORY_STORE.")
        return None
    try:
        from langchain_chroma import Chroma

        from app.config import get_embeddings, get_settings

        settings = get_settings()
        return Chroma(
            collection_name=_MEMORY_COLLECTION,
            embedding_function=get_embeddings(),
            persist_directory=settings.VECTORSTORE_DIR,
        )
    except Exception as exc:  # noqa: BLE001 - fail open, never crash a query over this
        log.warning("Memory store setup failed (%s). Queries run without memory.", exc)
        return None


def reset_for_tests() -> None:
    get_memory_store.cache_clear()
