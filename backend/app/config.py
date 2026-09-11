"""Central configuration + factory functions.

No business logic here — just loading settings and building configured client
objects. Every node takes its LLM, embeddings and vector store from here, so
swapping a model is a one-place change and mocking in tests is easy.
"""

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

    # --- models ------------------------------------------------------------
    # Grading and generation share one model. The small grading call is
    # latency-sensitive, hence Groq (very fast inference).
    LLM_MODEL: str = "openai/gpt-oss-120b"
    # FastEmbed's default — small, ONNX, runs offline, no API key.
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"

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
    # Where the BEIR download is extracted. Gitignored — committing ~5k abstracts
    # makes no sense when it is a reproducible download.
    BEIR_DIR: str = str(BACKEND_DIR / "beir")

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


@lru_cache
def get_llm(temperature: float = 0.0):
    """Configured ChatGroq.

    Defaults to temperature 0: grading and routing need determinism, not
    creativity. The `generate` node can override it.
    """
    from langchain_groq import ChatGroq

    s = get_settings()
    if not s.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Create `.env` in the repo root (copy "
            ".env.example) and add a key from https://console.groq.com."
        )
    return ChatGroq(
        model=s.LLM_MODEL,
        temperature=temperature,
        api_key=s.GROQ_API_KEY,
    )


@lru_cache
def get_embeddings():
    """FastEmbed embeddings — a local ONNX model, no API calls.

    Downloads once (~100 MB), cached afterwards.
    """
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings

    return FastEmbedEmbeddings(model_name=get_settings().EMBEDDING_MODEL)


@lru_cache
def get_vectorstore():
    """Handle to the persisted Chroma collection.

    Embedded mode — no separate database service, just a directory. The same
    directory the ingestion script writes and the `retrieve` node reads.
    """
    from langchain_chroma import Chroma

    s = get_settings()
    return Chroma(
        collection_name=s.collection_name,
        embedding_function=get_embeddings(),
        persist_directory=s.VECTORSTORE_DIR,
    )
