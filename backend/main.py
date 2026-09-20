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

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import active_corpus, get_settings, set_current_corpus
from app.graph.build_graph import build_crag_graph, run_query_stream
from app.logging_config import configure_json_logging
from app.rate_limit import RateLimiter
from app.memory.episodic import (
    format_episodes_for_prompt,
    recall_similar,
    record_episode_from_state,
)
from app.memory.semantic import format_facts_for_prompt, recall_facts
from app.schemas.crag_state import initial_state
from app.token_usage import new_tracker


def _state_with_memory(question: str) -> dict:
    """`initial_state` plus `memory_note` - kept out of `initial_state` itself
    so that function stays a pure schema constructor with no I/O, and both
    `/api/query` and `/api/query/stream` compute this identically before
    invoking the graph. See app/memory/episodic.py and semantic.py."""
    state = initial_state(question)
    episodes = recall_similar(question)
    facts = recall_facts(question)
    state["memory_note"] = format_facts_for_prompt(facts) or format_episodes_for_prompt(episodes)
    return state

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
# split setup (Vite on :5173, Nginx on :3001), so the default is
# those two origins rather than `*`. Override with CORS_ORIGINS for a split
# deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


# The endpoints that cost money or CPU. Read endpoints (`/health`, `/api/stats`,
# `/api/documents`) are left alone: the dashboard hits them on every page load
# and they make no LLM call.
_QUERY_LIMITER = RateLimiter(limit=15, window_seconds=60)
_UPLOAD_LIMITER = RateLimiter(limit=5, window_seconds=300)


def _client_key(request: Request) -> str:
    """Who to count against. Cloud Run terminates TLS and forwards the caller in
    X-Forwarded-For, so `request.client.host` alone is the load balancer and
    would rate-limit every visitor as one. First entry in the chain is the
    original client; it is spoofable, but the goal here is stopping an
    accidental or lazy loop, not defeating a determined attacker.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _enforce(limiter: RateLimiter, request: Request) -> None:
    key = _client_key(request)
    if not limiter.allow(key):
        raise HTTPException(
            status_code=429,
            detail="too many requests - this is a public demo with a real API bill",
            headers={"Retry-After": str(limiter.retry_after(key))},
        )


def _groq_rate_limit_error():
    """The Groq client's rate-limit exception, or None if the SDK is absent.

    Imported lazily and defensively: `groq` is a transitive dependency of
    `langchain-groq`, and an exception handler is not worth a hard import that
    could break startup if that ever changes.
    """
    try:
        from groq import RateLimitError

        return RateLimitError
    except Exception:  # noqa: BLE001
        return None


_GROQ_RATE_LIMIT = _groq_rate_limit_error()

if _GROQ_RATE_LIMIT is not None:

    @app.exception_handler(_GROQ_RATE_LIMIT)
    async def _upstream_throttled(request, exc):
        """Groq's own per-minute token limit, surfaced as 503 rather than 500.

        The free tier allows 8000 tokens a minute across the whole account, and
        a query costs roughly 2500, so a handful of people using the demo at
        once is enough to hit it. That is not a bug in this service and a 500
        says it is: the request was fine, the upstream model was momentarily
        unavailable, and retrying shortly works.

        The provider's message carries its own wait hint, but parsing prose for
        a number is brittle, so this advertises a flat 10s - inside the 60s
        window the limit resets on.
        """
        logger.warning("upstream rate limit: %s", exc)
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=503,
            headers={"Retry-After": "10"},
            content={
                "detail": (
                    "the language model is rate limited right now - "
                    "wait a few seconds and ask again"
                )
            },
        )


@app.exception_handler(ValueError)
async def _value_error_is_a_client_error(request, exc: ValueError):
    """A bad `corpus` reaches the app as a plain ValueError from
    `config.collection_for`, on the GET endpoints that take it as a query
    parameter rather than through `QueryIn`'s pattern. Without this it surfaces
    as a 500, which says "the server is broken" about a request the client got
    wrong. One handler rather than a try/except at each of the three call sites,
    so a fourth one cannot forget it.
    """
    from fastapi.responses import JSONResponse

    logger.warning("rejected request: %s", exc)
    return JSONResponse(status_code=400, content={"detail": str(exc)})


class QueryIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    # Which index to answer from. Empty means the configured default, so an
    # older client that does not send it keeps working.
    #
    # The pattern is not decoration: this value reaches `collection_for()`,
    # which interpolates it into a Chroma collection name. Chroma rejects
    # anything outside [a-zA-Z0-9._-] with an exception, so "../../etc" used to
    # surface as a 500 rather than a 422. Rejecting it here makes it a client
    # error, which is what it is. `:` is allowed for the `upload:<session>` form.
    corpus: str = Field(default="", max_length=32, pattern=r"^[a-zA-Z0-9_:.-]*$")


class QueryOut(BaseModel):
    answer: str
    source_type: str          # "vector_db" | "web_search" -> UI badge
    sources: List[str]        # filenames (local) or URLs (web) -> UI citations
    relevance_score: str      # "yes" | "no"                -> UI relevance pill
    transformed_query: str    # empty unless the fallback ran
    logs: List[str]           # node-by-node trace          -> UI trace viewer
    elapsed_ms: int
    token_usage: dict         # per-model tokens/cost for this query — see app/token_usage.py
    memory_note: str = ""     # precedent from similar past questions — see app/memory/


def _query_response(final: dict, elapsed_ms: int, token_usage: dict) -> QueryOut:
    """One function so `/api/query` and `/api/query/stream`'s final event build
    the same payload — building it twice is the kind of drift
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
        memory_note=final.get("memory_note", ""),
    )


@app.post("/api/query", response_model=QueryOut)
async def query(body: QueryIn, request: Request) -> QueryOut:
    _enforce(_QUERY_LIMITER, request)
    started = time.perf_counter()

    # One tracker per request via a contextvar (app/token_usage.py) — the LLM
    # clients are cached and shared across requests, so this is what keeps
    # concurrent requests' token counts from mixing. The corpus rides the same
    # mechanism: run_in_threadpool copies the context, so the retriever below
    # reads whichever index this request asked for.
    tracker = new_tracker()
    set_current_corpus(body.corpus)

    # graph.invoke is synchronous and blocks on LLM and search calls. Run it in a
    # threadpool so one slow request cannot stall the whole event loop.
    from starlette.concurrency import run_in_threadpool

    final = await run_in_threadpool(_graph.invoke, _state_with_memory(body.question))

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    usage = tracker.summary()

    from app.metrics import record_query

    record_query(final, usage, elapsed_ms, primary_model=get_settings().LLM_MODEL)
    record_episode_from_state(final)

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
async def query_stream(body: QueryIn, request: Request) -> StreamingResponse:
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

    _enforce(_QUERY_LIMITER, request)
    set_current_corpus(body.corpus)

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    SENTINEL = object()
    started = time.perf_counter()
    tracker = new_tracker()

    def produce() -> None:
        try:
            initial = _state_with_memory(body.question)
            for kind, payload in run_query_stream(body.question, graph=_graph, state=initial):
                if kind == "done":
                    elapsed_ms = int((time.perf_counter() - started) * 1000)
                    usage = tracker.summary()
                    from app.metrics import record_query

                    record_query(payload, usage, elapsed_ms, primary_model=get_settings().LLM_MODEL)
                    record_episode_from_state(payload)
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
        import contextlib

        from starlette.concurrency import run_in_threadpool

        # The producer runs as a task rather than being awaited here. Awaiting it
        # ran the whole graph to completion before the first event was yielded,
        # which is a non-streaming endpoint wearing an SSE content-type: measured
        # against the running server, every event arrived in one 0.43s burst
        # after 8.5s of work, with the `retrieve` event claiming elapsed_ms=2229.
        # Starting it concurrently and draining as it goes is the whole point of
        # the queue.
        worker = asyncio.create_task(run_in_threadpool(produce))
        try:
            while True:
                kind, payload = await queue.get()
                if kind is SENTINEL:
                    return
                yield f"event: {kind}\ndata: {json.dumps(payload)}\n\n"
        finally:
            # On a client disconnect the generator is closed mid-drain. The
            # worker thread cannot be cancelled (it is blocked in sync LLM
            # calls), but awaiting it surfaces any error instead of leaving the
            # task orphaned and its exception unretrieved.
            with contextlib.suppress(Exception):
                await worker

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


@app.post("/api/memory/consolidate")
async def consolidate_memory():
    """Manually run semantic-fact consolidation over recorded episodes.

    Deliberately not on a schedule inside this process - see the module
    docstring in app/memory/semantic.py for why this is a periodic, explicit
    job rather than something every query pays for.
    """
    from app.memory.semantic import consolidate_facts

    return {"facts_written": consolidate_facts()}


@app.get("/api/stats")
async def stats(corpus: str = ""):
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

    # The picker asks for a corpus; without one this reports the configured
    # default, which is what every caller did before the picker existed.
    set_current_corpus(corpus)
    s = get_settings()

    # On SciFact "documents" means the corpus's abstracts, not files — counting
    # the filesystem and reporting 7 would be a lie. But `None` was wrong too:
    # the real count is known, it just lives somewhere else. The stat card used
    # to show "—" while the same page said "500 documents" below it, and the
    # comment in `/api/documents` claimed stats provided the count when it did
    # not. Dedupe from the chunks: one abstract is split across several.
    if active_corpus() != "concepts":
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
    except Exception:  # noqa: BLE001 — the store may not exist yet
        chunks = 0

    # Eval results are optional — the UI has to work on a fresh clone that has
    # never run the eval. So a missing file means `None`, not zero: "not
    # measured" and "scored zero" are different claims and the UI has to be able
    # to tell them apart.
    evaluation = None
    # One results file per corpus. Concepts and SciFact numbers are different
    # things, and mixing them would make both meaningless.
    results_name = "results.json" if active_corpus() == "concepts" else f"results_{active_corpus()}.json"
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
        "corpus": active_corpus(),
        "documents": documents,
        "chunks": chunks,
        "evaluation": evaluation,
        "config": {
            "llm_model": s.LLM_MODEL,
            "embedding_model": s.EMBEDDING_MODEL,
            "reranker_model": s.RERANKER_MODEL if s.USE_RERANKER else None,
            "search_provider": s.SEARCH_PROVIDER,
            "top_k": s.TOP_K,
            "corpus": active_corpus(),
            "hybrid": s.USE_HYBRID,
            "reranker": s.USE_RERANKER,
            "groq_key_set": bool(s.GROQ_API_KEY),
        },
    }


@app.post("/api/upload")
async def upload(
    request: Request, session: str = Form(...), file: UploadFile = File(...)
):
    """Index one uploaded document into that session's own corpus.

    Scoped per session because the deployed demo is public: indexing into the
    shared corpus would let one visitor's document answer another's question.
    Query it back by passing `corpus=upload:<session>`.

    The work is CPU-bound (PDF parsing, then embedding every chunk), so it runs
    in a threadpool rather than blocking the event loop the way a large file
    otherwise would.

    The body is read in chunks and abandoned the moment it exceeds the limit.
    `await file.read()` with no argument would pull the whole upload into memory
    first and only then let `extract_text` reject it, so a rejected request cost
    as much memory as an accepted one: six concurrent 115 MB uploads took this
    container from 560 MiB to 1.2 GiB while every one of them correctly returned
    400. The deployed instance has 1 GiB and a concurrency of 8, so that is an
    out-of-memory kill from requests the API is already refusing.
    """
    from starlette.concurrency import run_in_threadpool

    from app.tools.uploads import MAX_UPLOAD_BYTES, UploadError, ingest_upload

    _enforce(_UPLOAD_LIMITER, request)

    pieces: list[bytes] = []
    total = 0
    while piece := await file.read(1024 * 1024):
        total += len(piece)
        if total > MAX_UPLOAD_BYTES:
            # 413, not 400: the request was well-formed, just too big.
            raise HTTPException(
                status_code=413,
                detail=f"file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
            )
        pieces.append(piece)
    blob = b"".join(pieces)

    try:
        result = await run_in_threadpool(
            ingest_upload, session, file.filename or "upload", blob
        )
    except UploadError as exc:
        # The user picked a file this cannot read; that is a 400, not a bug.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - the boundary has to be broad
        logger.exception("upload failed")
        raise HTTPException(status_code=500, detail=f"indexing failed: {exc}") from exc

    # A new document invalidates the BM25 index for this session's corpus only.
    # Clearing all of them would make one visitor's upload rebuild every other
    # session's index.
    from app.tools.bm25_search import bust_cache

    bust_cache(f"upload:{session}")
    return result


@app.delete("/api/upload/{session}")
async def clear_upload(session: str):
    """Drop everything a session uploaded, so the demo can be reset."""
    from app.tools.bm25_search import bust_cache
    from app.tools.uploads import clear_session

    clear_session(session)
    bust_cache(f"upload:{session}")
    return {"cleared": session}


@app.get("/api/documents/{doc_id}")
async def document_text(doc_id: str, corpus: str = ""):
    """The text of one indexed document.

    The grader's verdict is the project's central decision, and it is only
    checkable if the documents it read are readable too. Without this a `no`
    has to be taken on trust, which is the opposite of what the evaluation
    page is arguing for.

    Built-in documents are read from disk. Uploaded ones no longer exist as
    files - only as chunks - so they are reassembled from the index in chunk
    order.
    """
    from pathlib import Path

    from app.config import get_vectorstore

    set_current_corpus(corpus)

    if active_corpus() == "concepts":
        # Resolve inside the data directory and refuse anything that escapes it:
        # doc_id arrives from the client, and "../../etc/passwd" is the obvious
        # thing to try.
        data_dir = Path(get_settings().DATA_DIR).resolve()
        target = (data_dir / doc_id).resolve()
        if data_dir not in target.parents or not target.is_file():
            raise HTTPException(status_code=404, detail=f"no document '{doc_id}'")
        return {"id": doc_id, "text": target.read_text(encoding="utf-8")}

    try:
        raw = get_vectorstore()._collection.get(include=["documents", "metadatas"])
    except Exception:  # noqa: BLE001 - the collection may not exist yet
        raise HTTPException(status_code=404, detail=f"no document '{doc_id}'") from None

    pairs = [
        (meta or {}, text)
        for meta, text in zip(raw.get("metadatas") or [], raw.get("documents") or [])
        if (meta or {}).get("source") == doc_id
    ]
    if not pairs:
        raise HTTPException(status_code=404, detail=f"no document '{doc_id}'")

    pairs.sort(key=lambda p: p[0].get("chunk", 0))
    return {"id": doc_id, "text": "\n\n".join(text for _, text in pairs)}


@app.get("/api/documents")
async def documents(corpus: str = ""):
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

    set_current_corpus(corpus)
    s = get_settings()

    if active_corpus() == "concepts":
        data_dir = Path(s.DATA_DIR)
        if not data_dir.exists():
            return {"corpus": active_corpus(), "documents": []}

        # How many chunks each file became. A file list alone says nothing a
        # directory listing does not; the chunk count is what makes the page
        # about retrieval - it is the unit the retriever actually scores.
        counts: dict[str, int] = {}
        try:
            raw = get_vectorstore()._collection.get(include=["metadatas"])
            for meta in raw.get("metadatas") or []:
                src = (meta or {}).get("source")
                if src:
                    counts[src] = counts.get(src, 0) + 1
        except Exception:  # noqa: BLE001 - the collection may not exist yet
            counts = {}

        return {
            "corpus": active_corpus(),
            "documents": sorted(
                (
                    {
                        "id": p.name,
                        "title": p.stem.replace("_", " "),
                        "bytes": p.stat().st_size,
                        "chunks": counts.get(p.name),
                    }
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
    except Exception:  # noqa: BLE001 — the collection may not exist yet
        return {"corpus": active_corpus(), "documents": []}

    seen = {}
    for meta in raw.get("metadatas") or []:
        doc_id = (meta or {}).get("source")
        if doc_id and doc_id not in seen:
            seen[doc_id] = {"id": doc_id, "title": (meta or {}).get("title", ""), "bytes": None}

    # No point shipping the whole list — 500 abstracts would flood the UI. The
    # count comes from `/api/stats`; this is a sample.
    docs = list(seen.values())
    return {
        "corpus": active_corpus(),
        "total": len(docs),
        "documents": docs[:60],
        "truncated": len(docs) > 60,
    }


# Mounted last: a mount at "/" swallows every path beneath
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
