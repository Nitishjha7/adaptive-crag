"""Central configuration + factory functions.

No business logic here, just loading settings and building configured client
objects. Every node takes its LLM, embeddings and vector store from here, so
swapping a model is a one-place change and mocking in tests is easy.
"""

import re
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent
# repo root — where .env lives, shared with docker-compose
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Typed .env loader. A missing key fails at first use, not silently."""

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- secrets -----------------------------------------------------------
    GROQ_API_KEY: str = ""
    TAVILY_API_KEY: str = ""

    # --- serving -----------------------------------------------------------
    CORS_ORIGINS: str = "http://localhost:3001,http://localhost:5173"
    """Comma-separated origins allowed to call the API.

    The default is the two local dev origins, **not** `*`. The deploy image
    serves the built frontend from this same app, so in production there is no
    cross-origin caller at all and this list stays unused, which is exactly
    why the permissive default was worth removing rather than keeping "just in
    case". Set it only for a split deployment.
    """

    # --- models ------------------------------------------------------------
    # Grading and generation share one model. The small grading call is
    # latency-sensitive, hence Groq (very fast inference).
    LLM_MODEL: str = "openai/gpt-oss-120b"
    # FastEmbed's default — small, ONNX, runs offline, no API key.
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"

    # A gateway needs somewhere to fail over *to*. Empty by default, since a single
    # model is the honest default for a project with one Groq key, and this
    # only turns on when a fallback list is actually configured. See
    # get_llm() for why this is Groq model ids, not other providers: this
    # account has one key, one vendor, so a genuine multi-provider gateway is
    # not being simulated here.
    LLM_FALLBACK_MODELS: str = ""

    # --- retrieval ---------------------------------------------------------
    VECTOR_DB: str = "chroma"
    # "duckduckgo" (no key needed) or "tavily" (better snippets, needs a signup)
    SEARCH_PROVIDER: str = "duckduckgo"
    # --- which corpus is loaded -------------------------------------------
    # "concepts" — 7 hand-written RAG/agent docs (22 chunks). Small, and its gap
    #               is **categorical**, which keeps the demo predictable. The
    #               fixed demo queries and the 20/20 eval run on this.
    # "scifact"   — BEIR SciFact, ~5k scientific abstracts. Large enough for
    #               ranking to matter, and its **qrels ship with the dataset**, so
    #               the labels are not mine. That removes the structural bias the
    #               concepts eval admits to in RESULTS.md.
    #
    # They live in separate Chroma collections, so they cannot contaminate each
    # other and switching does not require a re-ingest.
    CORPUS: str = "concepts"
    TOP_K: int = 4

    # --- hybrid retrieval + reranking (Phase 9) ----------------------------
    # Both behind flags, defaulting on, so the eval can turn them off and
    # **measure the delta**. In this project a feature whose benefit cannot be
    # shown is not a feature.
    USE_HYBRID: bool = True
    USE_RERANKER: bool = True

    # How many candidates to fetch before reranking. Must exceed TOP_K, or the
    # reranker has nothing to choose from and becomes a no-op.
    RETRIEVAL_CANDIDATES: int = 8

    RERANKER_MODEL: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100

    # --- paths -------------------------------------------------------------
    # Mounted as a volume in Docker so the index survives container restarts.
    VECTORSTORE_DIR: str = str(BACKEND_DIR / "vectorstore")
    DATA_DIR: str = str(BACKEND_DIR / "data")
    # Where the BEIR download is extracted. Gitignored, since committing ~5k abstracts
    # makes no sense when it is a reproducible download.
    BEIR_DIR: str = str(BACKEND_DIR / "beir")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def fallback_model_list(self) -> list[str]:
        return [m.strip() for m in self.LLM_FALLBACK_MODELS.split(",") if m.strip()]

    @property
    def collection_name(self) -> str:
        """One Chroma collection per corpus.

        Separate collections so the two corpora cannot **mix** — otherwise the 22
        concepts chunks would surface inside SciFact retrieval and both sets of
        eval numbers would be worthless.

        Side benefit: switching needs no re-ingest, because both indexes sit in
        the same `vectorstore/` directory.
        """
        return "crag_docs" if self.CORPUS == "concepts" else f"crag_{self.CORPUS}"


@lru_cache
def get_settings() -> Settings:
    """One Settings instance per process, so the env is parsed once."""
    return Settings()


def _client(model: str, temperature: float, settings: Settings):
    from langchain_groq import ChatGroq

    from .token_usage import TRACKING_CALLBACK

    return ChatGroq(
        model=model,
        temperature=temperature,
        api_key=settings.GROQ_API_KEY,
        # Bound once, here, rather than passed at every one of the four call
        # sites (grade_documents, transform_query, generate, validators) —
        # see app/token_usage.py for why one stateless callback shared across
        # every cached client is the right scope.
        callbacks=[TRACKING_CALLBACK],
    )


@lru_cache
def get_llm(temperature: float = 0.0):
    """Configured ChatGroq — a fallback chain when one is configured, a
    single client otherwise.

    Defaults to temperature 0: grading and routing need determinism, not
    creativity. The `generate` node can override it. Cached per temperature,
    so the grader/router calls (0.0) and any caller wanting slack share one
    client rather than opening a fresh one each time.

    The gateway covers retired model ids, which Groq does without much
    notice. A retired or saturated model is not a bug in this code, and none
    of the four call sites below can tell "the model is gone" apart from "my
    prompt is wrong" unless something sits in front of the client and retries
    elsewhere.

    `with_fallbacks` was chosen over a hand-rolled try/except around every
    call site because it returns something that still satisfies the plain
    `Runnable` interface every caller already depends on (`.invoke(...)` via
    a `ChatPromptTemplate | get_llm(...)` chain) — no call site has to know
    whether it got a plain `ChatGroq` or a fallback chain.

    **Only one provider.** `LLM_FALLBACK_MODELS` is a list of Groq model ids,
    not other vendors. This account has one Groq key, so a genuine
    multi-provider gateway would need a second vendor's key this project does
    not have. Falling over to a second Groq model is real protection against
    a retired or rate-limited model id; it is not protection against Groq
    itself being down.
    """
    settings = get_settings()
    if not settings.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Create `.env` in the repo root (copy "
            ".env.example) and add a key from https://console.groq.com."
        )

    primary = _client(settings.LLM_MODEL, temperature, settings)
    fallback_ids = [m for m in settings.fallback_model_list if m != settings.LLM_MODEL]
    if not fallback_ids:
        return primary

    fallbacks = [_client(m, temperature, settings) for m in fallback_ids]
    # Temperature is passed to every client in the chain, primary and
    # fallback alike. The grading/routing determinism this project relies on
    # (temp=0) holds regardless of which model in the chain actually answers.
    return primary.with_fallbacks(fallbacks)


@lru_cache
def get_embeddings():
    """FastEmbed embeddings — a local ONNX model, no API calls.

    Downloads once (~100 MB), cached afterwards.
    """
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings

    return FastEmbedEmbeddings(model_name=get_settings().EMBEDDING_MODEL)


# Which corpus this request is reading. CORPUS in the environment is the
# default; a request may override it, and the API serves concurrent requests,
# so a module global would let one request answer from another's index.
_CURRENT_CORPUS: ContextVar[str | None] = ContextVar("crag_corpus", default=None)


def set_current_corpus(corpus: str | None) -> None:
    """Pin this request to a corpus. Called once, by the API layer."""
    _CURRENT_CORPUS.set(corpus or None)


def active_corpus() -> str:
    """The corpus this request reads: the override, else the configured one."""
    return _CURRENT_CORPUS.get() or get_settings().CORPUS


_SAFE_CORPUS = re.compile(r"[a-zA-Z0-9._-]+")


def collection_for(corpus: str) -> str:
    """One Chroma collection per corpus - see Settings.collection_name.

    ``upload:<session>`` addresses a session's own uploaded documents. Routing it
    through the same function means the retriever, BM25 and the stats endpoints
    all follow an upload without any of them knowing uploads exist.
    """
    if corpus.startswith("upload:"):
        from app.tools.uploads import session_collection

        return session_collection(corpus.split(":", 1)[1])
    if corpus == "concepts":
        return "crag_docs"
    # The upload branch above sanitises through `session_collection`; this one
    # used to interpolate the raw value, so a corpus of "../../etc" reached
    # Chroma and came back as an unhandled exception (a 500 on `/api/query`).
    # Chroma accepts [a-zA-Z0-9._-]; anything else is a client error.
    if not _SAFE_CORPUS.fullmatch(corpus):
        raise ValueError(f"invalid corpus name: {corpus!r}")
    return f"crag_{corpus}"


@lru_cache
def _vectorstore_for(collection: str):
    """One handle per collection. Cached on the collection name rather than on
    nothing, so switching corpus does not hand back the previous index."""
    from langchain_chroma import Chroma

    return Chroma(
        collection_name=collection,
        embedding_function=get_embeddings(),
        persist_directory=get_settings().VECTORSTORE_DIR,
    )


def reset_vectorstore_cache() -> None:
    """Drop the cached handles. Ingestion calls this after writing, so the next
    read sees the new chunks rather than a handle opened before them."""
    _vectorstore_for.cache_clear()


def get_vectorstore():
    """Handle to the persisted Chroma collection for the active corpus.

    Embedded mode — no separate database service, just a directory. The same
    directory the ingestion script writes and the `retrieve` node reads.
    """
    return _vectorstore_for(collection_for(active_corpus()))
