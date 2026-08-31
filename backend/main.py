"""FastAPI entrypoint — Phase 5.

`POST /api/query` graph invoke karta hai aur answer ke saath `source_type`,
`relevance_score`, aur poora step-by-step trace lautata hai. Trace hi is project
ka sabse dikhne wala hissa hai: frontend usse node-by-node timeline render karta
hai, jisse system black box nahi rehta — dikhta hai ki route kyun liya gaya.
"""

import time
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import get_settings
from app.graph.build_graph import build_crag_graph
from app.schemas.crag_state import initial_state

# Module load pe ek baar compile — har request pe graph dobara banana bewajah kaam hai.
_graph = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph
    _graph = build_crag_graph()
    yield


app = FastAPI(title="Adaptive CRAG", version="0.5.0", lifespan=lifespan)

# Dev me khula. Production me frontend domain tak restrict karna hai — abhi
# frontend ka origin pata nahi hai, isliye TODO chhoda hai (Phase 7).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO(Phase 7): deploy pe frontend origin tak seemit karo
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class QueryIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class QueryOut(BaseModel):
    answer: str
    source_type: str          # "vector_db" | "web_search" -> UI badge
    relevance_score: str      # "yes" | "no"                -> UI relevance pill
    transformed_query: str    # khaali agar fallback nahi chala
    logs: List[str]           # node-by-node trace          -> UI trace viewer
    elapsed_ms: int


@app.post("/api/query", response_model=QueryOut)
async def query(body: QueryIn) -> QueryOut:
    started = time.perf_counter()

    # graph.invoke sync hai aur LLM/search calls pe block karta hai. Threadpool me
    # bhejte hain taaki ek slow request poora event loop na rok de.
    from starlette.concurrency import run_in_threadpool

    final = await run_in_threadpool(_graph.invoke, initial_state(body.question))

    return QueryOut(
        # final_output guardrails node bharta hai; generation defensive fallback hai.
        answer=final.get("final_output") or final.get("generation") or "",
        source_type=final.get("source_type", ""),
        relevance_score=final.get("relevance_score", ""),
        transformed_query=final.get("transformed_query", ""),
        logs=final.get("logs", []),
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )


@app.get("/health")
async def health():
    """Docker healthcheck. Jaan-boojh ke koi LLM call nahi karta — health endpoint
    ko sasta aur bharosemand hona chahiye, warna rate limit hi container ko
    unhealthy mark karwa dega."""
    from app.tools.vector_search import collection_count

    s = get_settings()
    try:
        chunks = collection_count()
    except Exception:  # noqa: BLE001 — store abhi bana hi na ho
        chunks = 0

    return {
        "status": "ok",
        "indexed_chunks": chunks,
        "search_provider": s.SEARCH_PROVIDER,
        "llm_model": s.LLM_MODEL,
        "groq_key_set": bool(s.GROQ_API_KEY),
    }
