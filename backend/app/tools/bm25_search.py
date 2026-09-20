"""BM25 keyword search over the same corpus Chroma holds.

**Why, when vector search already exists:** the two are strong at different
things.

Vector search captures *meaning* — "annual time off" and "paid leave
entitlement" land near each other without sharing a word. It is surprisingly
weak on exact tokens, though: `EMP-4582` and `EMP-4583` sit almost on top of each
other in embedding space, because they *mean* the same thing.

BM25 is the opposite. It matches exact terms and uses IDF to weight rare ones, so
it wins on identifiers, product codes, version numbers and proper nouns.

Production RAG runs both and fuses the results. Same pattern as `web_search.py` —
one interface, several implementations.

**Its benefit on this corpus is limited, and that is worth admitting:** seven
concept documents contain no SKUs and no employee IDs, so BM25 will mostly
surface the chunks vector search already found. Hence the `USE_HYBRID` flag and
an eval that measures it rather than assuming it.
"""

import re
from typing import List, Optional, Tuple

from app.config import active_corpus, get_settings, get_vectorstore

# Simple tokenizer: lowercase, alphanumeric runs. No stemming —
# the benefit of another dependency (nltk/snowball) could not be measured on 22
# chunks, and this project only adds what it can measure.
_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> List[str]:
    return _TOKEN.findall(text.lower())


# Keyed by corpus, so one corpus can be dropped without discarding the others.
# `lru_cache` cannot evict a single key - only `cache_clear()`, which throws away
# every corpus - and on a public demo one visitor's upload would then force every
# other session to rebuild its index.
_INDEX_CACHE: dict = {}


def _build_index(corpus: str):
    """Load the whole corpus into memory and build the BM25 index.

    **Why the whole corpus:** BM25's IDF depends on a term's *corpus-wide*
    frequency. Running BM25 over only the top-k chunks would compute the wrong
    IDF and produce meaningless scores.

    Trivial at 22 chunks. This approach does not scale — a large corpus needs a
    real inverted index (Elasticsearch / OpenSearch / Tantivy). The limitation is
    real and is written down in the docs.

    Keyed on the corpus, so switching does not hand back the previous index.
    Built once per corpus; cleared after ingestion - see `bust_cache()`.
    """
    if corpus in _INDEX_CACHE:
        return _INDEX_CACHE[corpus]

    from rank_bm25 import BM25Okapi

    store = get_vectorstore()
    # Ask for "documents" and "metadatas" only — embeddings are large and BM25
    # has no use for them.
    raw = store._collection.get(include=["documents", "metadatas"])

    texts = raw.get("documents") or []
    metas = raw.get("metadatas") or [{}] * len(texts)
    sources = [(m or {}).get("source", "unknown") for m in metas]

    if not texts:
        # Not cached: an empty corpus usually means ingestion has not run yet,
        # and caching that would keep returning nothing after it does.
        return None, [], []

    built = (BM25Okapi([tokenize(t) for t in texts]), texts, sources)
    _INDEX_CACHE[corpus] = built
    return built


def bust_cache(corpus: str | None = None) -> None:
    """Drop a stale index after ingestion.

    With a corpus, drops only that one. Uploading a document invalidates that
    session's index and nothing else, so a visitor's upload no longer makes
    every other session rebuild.

    Without one, drops everything - which is what `ingest.py` wants, since a
    re-ingest can rewrite any collection.
    """
    if corpus is None:
        _INDEX_CACHE.clear()
    else:
        _INDEX_CACHE.pop(corpus, None)


def bm25_search(query: str, k: Optional[int] = None) -> List[Tuple[str, str]]:
    """Top-k `(text, source)` pairs by BM25 score.

    Returns an empty list on an empty corpus rather than raising. In hybrid
    retrieval BM25 is an *additional* signal; its failure should not take the
    whole retrieval down.
    """
    k = k or get_settings().TOP_K
    index, texts, sources = _build_index(active_corpus())
    if index is None:
        return []

    scores = index.get_scores(tokenize(query))

    # Drop zero-score chunks: in BM25 a 0 means not one query term appears in
    # that chunk. Ranking those would only add noise to the fusion.
    ranked = sorted(
        (i for i, s in enumerate(scores) if s > 0),
        key=lambda i: scores[i],
        reverse=True,
    )[:k]

    return [(texts[i], sources[i]) for i in ranked]
