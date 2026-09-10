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
    sources: List[str]        # filenames (local) ya URLs (web)  -> UI citations
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
        sources=final.get("sources", []),
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


@app.get("/api/stats")
async def stats():
    """Dashboard ke stat cards + System Info / Evaluation tabs ke liye.

    Sab kuch **asli source** se aata hai — corpus files gine jaate hain, chunk
    count Chroma se, aur eval numbers `eval/results.json` se jo asli run ne
    likhi thi. Yahan koi number hardcode nahi hai; agar eval dobara chale aur
    result badle, UI apne aap badal jaayega.

    `/health` ki tarah ye bhi **koi LLM call nahi** karta — dashboard har page
    load pe isse hit karta hai.
    """
    import json
    from pathlib import Path

    from app.config import BACKEND_DIR
    from app.tools.vector_search import collection_count

    s = get_settings()

    # SciFact pe "documents" ka matlab corpus ke abstracts hain, files nahi —
    # wahan filesystem gin ke 7 bolna jhooth hoga.
    if s.CORPUS != "concepts":
        documents = None
    else:
        data_dir = Path(s.DATA_DIR)
        documents = (
            len([
                p for p in data_dir.iterdir()
                if p.suffix.lower() in {".md", ".txt"} and p.name.lower() != "readme.md"
            ])
            if data_dir.exists()
            else 0
        )

    try:
        chunks = collection_count()
    except Exception:  # noqa: BLE001 — store abhi bana hi na ho
        chunks = 0

    # Eval results optional hain — repo clone karke bina eval chalaye bhi UI
    # chalni chahiye. Isliye missing file pe `None`, zero nahi: "measure nahi
    # hua" aur "zero score" do alag baatein hain, aur UI ko farak pata hona chahiye.
    evaluation = None
    # Per-corpus results file — concepts aur scifact ke numbers alag hain aur
    # unhe mix karna dono ko meaningless bana dega.
    results_name = "results.json" if s.CORPUS == "concepts" else f"results_{s.CORPUS}.json"
    results_path = BACKEND_DIR / "eval" / results_name
    if results_path.exists():
        try:
            summary = json.loads(results_path.read_text(encoding="utf-8"))["summary"]
            evaluation = {
                "routing_correct": summary.get("routing_correct"),
                "routing_total": summary.get("scored"),
                "routing_accuracy_pct": summary.get("routing_accuracy_pct"),
                "missed_fallbacks": summary.get("missed_fallbacks"),
                "unnecessary_fallbacks": summary.get("unnecessary_fallbacks"),
                "groundedness_pass_pct": summary.get("groundedness_pass_pct"),
                "llm_calls_local": summary.get("llm_calls_local_route"),
                "llm_calls_web": summary.get("llm_calls_web_route"),
                "ambiguous_cases": summary.get("ambiguous_cases"),
                "ambiguous_stability_pct": summary.get("ambiguous_stability_pct"),
                # Sirf BEIR pe milta hai — wahan qrels se pata hai ki sahi doc
                # kaunsa tha. Concepts corpus pe ground truth hi nahi, to None.
                "recall_at_k_pct": summary.get("recall_at_k_pct"),
            }
        except Exception:  # noqa: BLE001 — corrupt/partial file UI na tode
            evaluation = None

    return {
        "corpus": s.CORPUS,
        "documents": documents,
        "chunks": chunks,
        "evaluation": evaluation,
        "config": {
            "llm_model": s.LLM_MODEL,
            "embedding_model": s.EMBEDDING_MODEL,
            "reranker_model": s.RERANKER_MODEL if s.USE_RERANKER else None,
            "search_provider": s.SEARCH_PROVIDER,
            "top_k": s.TOP_K,
            "corpus": s.CORPUS,
            "hybrid": s.USE_HYBRID,
            "reranker": s.USE_RERANKER,
            "groq_key_set": bool(s.GROQ_API_KEY),
        },
    }
