"""Central configuration + factory functions.

Koi business logic yahan nahi hai — sirf settings load karna aur configured
client objects banana. Har node yahin se LLM / embeddings / vectorstore uthata
hai, taaki model swap ek jagah se ho jaye aur test me mock karna easy rahe.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent
# repo root (yahan .env rehti hai, docker-compose ke saath share hoti hai)
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Typed .env loader. Missing key pe crash hota hai jab pehli baar use ho."""

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- secrets -----------------------------------------------------------
    GROQ_API_KEY: str = ""
    TAVILY_API_KEY: str = ""

    # --- models ------------------------------------------------------------
    # Grading aur generation dono isi model se. Chhota grading call latency-
    # sensitive hai, isliye Groq (bahut fast inference).
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    # FastEmbed ka default — chhota, ONNX, offline chalta hai, API key nahi chahiye.
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"

    # --- retrieval ---------------------------------------------------------
    VECTOR_DB: str = "chroma"
    # "duckduckgo" (koi key nahi chahiye) ya "tavily" (behtar snippets, signup chahiye)
    SEARCH_PROVIDER: str = "duckduckgo"
    COLLECTION_NAME: str = "crag_docs"
    TOP_K: int = 4
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100

    # --- paths -------------------------------------------------------------
    # Docker me ye volume pe mount hota hai, taaki index rebuild na karna pade.
    VECTORSTORE_DIR: str = str(BACKEND_DIR / "vectorstore")
    DATA_DIR: str = str(BACKEND_DIR / "data")


@lru_cache
def get_settings() -> Settings:
    """Ek hi Settings instance poore process me (env baar baar parse na ho)."""
    return Settings()


@lru_cache
def get_llm(temperature: float = 0.0):
    """Configured ChatGroq.

    temperature=0 default — grading aur routing me determinism chahiye,
    creativity nahi. `generate` node isko override kar sakta hai.
    """
    from langchain_groq import ChatGroq

    s = get_settings()
    if not s.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY set nahi hai. Repo root me `.env` bana (.env.example copy kar) "
            "aur https://console.groq.com se key daal."
        )
    return ChatGroq(
        model=s.LLM_MODEL,
        temperature=temperature,
        api_key=s.GROQ_API_KEY,
    )


@lru_cache
def get_embeddings():
    """FastEmbed embeddings — local ONNX model, koi API call nahi.

    Pehli baar model download hota hai (~100MB), uske baad cached.
    """
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings

    return FastEmbedEmbeddings(model_name=get_settings().EMBEDDING_MODEL)


@lru_cache
def get_vectorstore():
    """Persisted Chroma collection ka handle.

    Embedded mode — alag DB service nahi, bas ek directory. Wahi directory
    ingestion script likhti hai aur `retrieve` node padhta hai.
    """
    from langchain_chroma import Chroma

    s = get_settings()
    return Chroma(
        collection_name=s.COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=s.VECTORSTORE_DIR,
    )
