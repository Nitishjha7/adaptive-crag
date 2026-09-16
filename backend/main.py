"""FastAPI entrypoint.

`POST /api/query` invokes the graph and returns the answer together with
`source_type`, `relevance_score` and the full step-by-step trace. The trace is
the most visible part of this project: the frontend renders it as a node-by-node
timeline under each answer, so the system is not a black box — you can see why a
route was taken.
"""

import logging
import time
from pathlib import Path
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import get_settings
from app.graph.build_graph import build_crag_graph, run_query_stream
from app.logging_config import configure_json_logging
from app.schemas.crag_state import initial_state
from app.token_usage import new_tracker

# Configured before any module-level `logging.getLogger(...)` call below does
# its first logging — see app/logging_config.py.
configure_json_logging()
logger = logging.getLogger("app.main")

# Compiled once at module load — rebuilding the graph per request is wasted work.
_graph = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph
    _graph = build_crag_graph()
    yield


app = FastAPI(
    title="Adaptive CRAG",
    version="0.9.0",
    lifespan=lifespan,
)

# The deploy image serves the built frontend from this same app, so production
# is same-origin and this middleware never fires there. It exists for the local
# split setup (Vite on :5173, Nginx on :3001) — which is why the default is
# those two origins rather than `*`. Override with CORS_ORIGINS for a split
# deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class QueryIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class QueryOut(BaseModel):
    answer: str
    source_type: str          # "vector_db" | "web_search" -> UI badge
    sources: List[str]        # filenames (local) or URLs (web) -> UI citations
    relevance_score: str      # "yes" | "no"                -> UI relevance pill
    transformed_query: str    # empty unless the fallback ran
    logs: List[str]           # node-by-node trace          -> UI trace viewer
    elapsed_ms: int
    token_usage: dict         # per-model tokens/cost for this query — see app/token_usage.py


def _query_response(final: dict, elapsed_ms: int, token_usage: dict) -> QueryOut:
    """One function so `/api/query` and `/api/query/stream`'s final event build
    the exact same payload — building it twice is exactly the kind of drift
    that would make a streamed result quietly disagree with the non-streamed
    one."""
    return QueryOut(
        # final_output is written by the guardrails node; generation is the fallback.
        answer=final.get("final_output") or final.get("generation") or "",
        source_type=final.get("source_type", ""),
        sources=final.get("sources", []),
        relevance_score=final.get("relevance_score", ""),
        transformed_query=final.get("transformed_query", ""),
        logs=final.get("logs", []),
        elapsed_ms=elapsed_ms,
        token_usage=token_usage,
    )


@app.post("/api/query", response_model=QueryOut)
async def query(body: QueryIn) -> QueryOut:
    started = time.perf_counter()

    # One tracker per request via a contextvar (app/token_usage.py) — the LLM
    # clients are cached and shared across requests, so this is what keeps
    # concurrent requests' token counts from mixing.
    tracker = new_tracker()

    # graph.invoke is synchronous and blocks on LLM and search calls. Run it in a
    # threadpool so one slow request cannot stall the whole event loop.
    from starlette.concurrency import run_in_threadpool

    final = await run_in_threadpool(_graph.invoke, initial_state(body.question))

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    usage = tracker.summary()

    from app.metrics import record_query

    record_query(final, usage, elapsed_ms, primary_model=get_settings().LLM_MODEL)

    logger.info(
        "query completed",
        extra={
            "route": final.get("source_type", ""),
            "relevance_score": final.get("relevance_score", ""),
            "guardrail_passed": final.get("guardrail_passed"),
            "elapsed_ms": elapsed_ms,
            "total_tokens": usage.get("total_tokens", 0),
            "total_cost_usd": usage.get("total_cost_usd"),
        },
    )

    return _query_response(final, elapsed_ms, usage)


@app.post("/api/query/stream")
async def query_stream(body: QueryIn) -> StreamingResponse:
    """Same query as `/api/query`, as Server-Sent Events.

    The correction path (grade -> transform_query -> web_search_fallback ->
    generate) takes noticeably longer than a local hit, and `/api/query` makes
    both look identical to the caller until the whole thing is done. This
    streams a `progress` event the instant each graph node finishes — the
    corrective routing decision becoming visible as it happens is this
    project's actual story — then a final `done` event carrying the exact
    payload `/api/query` would have returned in one shot (`_query_response`,
    used by both).

    `run_query_stream` is a plain generator wrapping `graph.stream(...)`; the
    queue and background thread below exist only to get a synchronous
    generator's output onto the async event loop without blocking it — the
    same problem `run_in_threadpool` solves for the non-streaming endpoint.
    """
    import asyncio
    import json

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    SENTINEL = object()
    started = time.perf_counter()
    tracker = new_tracker()

    def produce() -> None:
        try:
            for kind, payload in run_query_stream(body.question, graph=_graph):
                if kind == "done":
                    elapsed_ms = int((time.perf_counter() - started) * 1000)
                    usage = tracker.summary()
                    from app.metrics import record_query

                    record_query(payload, usage, elapsed_ms, primary_model=get_settings().LLM_MODEL)
                    payload = _query_response(payload, elapsed_ms, usage).model_dump()
                asyncio.run_coroutine_threadsafe(queue.put((kind, payload)), loop).result()
        except Exception as exc:  # noqa: BLE001 - reported to the client as an event, not a 500
            logger.exception("Streaming query failed")
            asyncio.run_coroutine_threadsafe(
                queue.put(("error", {"detail": str(exc)})), loop
            ).result()
        finally:
            asyncio.run_coroutine_threadsafe(queue.put((SENTINEL, None)), loop).result()

    async def event_source():
        from starlette.concurrency import run_in_threadpool

        await run_in_threadpool(produce)
        # produce() has already fully populated the queue by the time
        # run_in_threadpool returns (each put is awaited via
        # run_coroutine_threadsafe before the next one), so draining it here
        # is sequential, not racy.
        while True:
            kind, payload = await queue.get()
            if kind is SENTINEL:
                return
            yield f"event: {kind}\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus scrape target — see app/metrics.py for what is tracked and
    why: routing, groundedness, LLM calls/tokens/cost, and gateway fallbacks,
    mirroring exactly what eval/RESULTS.md already argues about offline."""
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health():
    """Docker healthcheck. Deliberately makes no LLM call — a health endpoint has
    to be cheap and reliable, or one rate limit marks the container unhealthy and
    Docker restarts it in a loop."""
    from app.tools.vector_search import collection_count

    s = get_settings()
    try:
        chunks = collection_count()
    except Exception:  # noqa: BLE001 — the store may not exist yet
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
    """Feeds the dashboard's Evaluation and System views.

    Every value comes from a **real source** — documents counted for real, chunk
    count from Chroma, eval numbers read out of the JSON an actual run wrote.
    Nothing here is hardcoded, so re-running the eval changes the UI on its own.

    Like `/health`, this makes **no LLM call** — the dashboard hits it on every
    page load.
    """
    import json
    from pathlib import Path

    from app.config import BACKEND_DIR
    from app.tools.vector_search import collection_count

    s = get_settings()

    # On SciFact "documents" means the corpus's abstracts, not files — counting
    # the filesystem and reporting 7 would be a lie. But `None` was wrong too:
    # the real count is known, it just lives somewhere else. The stat card used
    # to show "—" while the same page said "500 documents" below it, and the
    # comment in `/api/documents` claimed stats provided the count when it did
    # not. Dedupe from the chunks: one abstract is split across several.
    if s.CORPUS != "concepts":
        try:
            from app.config import get_vectorstore

            raw = get_vectorstore()._collection.get(include=["metadatas"])
            sources = {
                (m or {}).get("source")
                for m in (raw.get("metadatas") or [])
                if (m or {}).get("source")
            }
            documents = len(sources) or None
        except Exception:  # noqa: BLE001 — the collection may not exist yet
            # Here `None` is right: it genuinely could not be determined.
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

    # Eval results are optional — the UI has to work on a fresh clone that has
    # never run the eval. So a missing file means `None`, not zero: "not
    # measured" and "scored zero" are different claims and the UI has to be able
    # to tell them apart.
    evaluation = None
    # One results file per corpus. Concepts and SciFact numbers are different
    # things, and mixing them would make both meaningless.
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
                # Only available on BEIR, where qrels say which document was
                # correct. The concepts corpus has no ground truth, so: None.
                "recall_at_k_pct": summary.get("recall_at_k_pct"),
                # Whether the answer was **right**, which neither routing nor
                # groundedness tells you. SciFact only, because that is where the
                # dataset ships its own SUPPORT/CONTRADICT label.
                "answer_verdict_pct": summary.get("answer_verdict_pct"),
                "answer_verdict_checked": summary.get("answer_verdict_checked"),
                "answer_verdict_given_gold_pct": summary.get("answer_verdict_given_gold_pct"),
            }
        except Exception:  # noqa: BLE001 — a corrupt file must not break the UI
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


@app.get("/api/documents")
async def documents():
    """What is in the index — the source for the UI's Documents view.

    Two different sources, because the corpora have different shapes:

    - `concepts` — from the filesystem, where documents are real files and the
      filename is the citation.
    - BEIR — from Chroma metadata, where there are no files at all; documents
      come from inside the dataset and are identified by `doc_id`.

    Like `/health` and `/api/stats`, **no LLM call**.
    """
    from pathlib import Path

    from app.config import get_vectorstore

    s = get_settings()

    if s.CORPUS == "concepts":
        data_dir = Path(s.DATA_DIR)
        if not data_dir.exists():
            return {"corpus": s.CORPUS, "documents": []}
        return {
            "corpus": s.CORPUS,
            "documents": sorted(
                (
                    {"id": p.name, "title": p.stem.replace("_", " "), "bytes": p.stat().st_size}
                    for p in data_dir.iterdir()
                    if p.suffix.lower() in {".md", ".txt"} and p.name.lower() != "readme.md"
                ),
                key=lambda d: d["id"],
            ),
        }

    # BEIR: pull unique documents out of the metadata. Dedupe is required because
    # one abstract is split across several chunks, and the UI wants documents.
    try:
        raw = get_vectorstore()._collection.get(include=["metadatas"])
    except Exception:  # noqa: BLE001 — collection abhi bana hi na ho
        return {"corpus": s.CORPUS, "documents": []}

    seen = {}
    for meta in raw.get("metadatas") or []:
        doc_id = (meta or {}).get("source")
        if doc_id and doc_id not in seen:
            seen[doc_id] = {"id": doc_id, "title": (meta or {}).get("title", ""), "bytes": None}

    # No point shipping the whole list — 500 abstracts would flood the UI. The
    # count comes from `/api/stats`; this is a sample.
    docs = list(seen.values())
    return {
        "corpus": s.CORPUS,
        "total": len(docs),
        "documents": docs[:60],
        "truncated": len(docs) > 60,
    }


# Mounted last, and deliberately so: a mount at "/" swallows every path beneath
# it, so every /api route above has to be registered first or it becomes
# unreachable.
#
# Only the single-service deploy image has this directory. Under docker-compose
# Nginx serves the frontend and this block is a no-op — the check is on the
# directory rather than an env var so there is one fewer thing to set correctly.
#
# The SPA keeps its view in the URL *hash* (`App.jsx`), so every route is the
# same document and `html=True` is all the fallback needed.
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
