# Adaptive Corrective RAG (CRAG) with Web Search Fallback

An agentic RAG system built with LangGraph that self-grades retrieved documents,
rewrites ambiguous queries, and falls back to live web search when local context is
insufficient — eliminating hallucinations from stale or irrelevant vector-store hits.

Naive RAG blindly trusts whatever the vector DB returns. CRAG adds a verification loop:
a grading node decides whether the retrieved chunks actually answer the question, and only
falls back to the web when they don't — so you get grounded answers without paying the
cost and latency of a web call on every query.

> ## Status: backend working end-to-end; no UI yet
>
> The corrective loop and the API are implemented and **verified against the real Groq
> API and live DuckDuckGo search**. All five fixed demo queries in
> [backend/data/README.md](backend/data/README.md) take the route they are supposed to
> (3 local, 2 web fallback).
>
> | Piece | State |
> |---|---|
> | Phase 1 — Chroma ingestion, config, controlled corpus | ✅ 7 docs → 22 chunks |
> | Phase 2 — `CRAGState`, LangGraph skeleton | ✅ |
> | Phase 3 — grading, conditional edge, query transform, web fallback | ✅ both routes verified live |
> | Phase 4 — groundedness + PII validation | ✅ |
> | Phase 5 — FastAPI `/api/query` + `/health` | ✅ |
> | Phase 6 — React UI (chat, source badge, relevance pill, trace viewer) | ✅ |
> | Phase 7 — `docker-compose.yml` (backend + Nginx frontend, `/api/` proxy) | ✅ |
> | Test suite — 27 tests (`.\dev.ps1 test`) | ✅ |
> | Evaluation harness — 20 labelled queries (`.\dev.ps1 eval`) | ✅ **routing 20/20, 0 missed fallbacks** |
> | Deployment (Render + Vercel) | ❌ not done |

## Measured: does the router actually route?

`backend/eval/` turns "routing looked right on the demo queries" into a number —
20 labelled questions, each marked for whether the local corpus genuinely answers it.

| Metric | Result |
|---|---|
| Routing accuracy | **20/20 (100%)**, stable across 3 runs |
| — on the 5 deliberately misleading cases | 5/5 |
| **Missed fallbacks** (answered locally when it should have searched) | **0** |
| Unnecessary fallbacks | 0 |
| Groundedness pass rate | 90–95% |
| **LLM calls per query** | **local 3.0 · web 4.0** |

Two things worth saying out loud, because the number alone flatters the system:

- **100% means the labelled task is easy, not that the router is perfect.** The
  corpus gap is categorical by design — concepts in, vendor/pricing/news out — so
  most web cases differ along an obvious axis. It does *not* show that routing
  survives an *ambiguous* gap, where the corpus half-covers a topic. [RESULTS.md](backend/eval/RESULTS.md)
  says what would make the eval genuinely hard.
- **The cost argument rests on call counts, not latency.** Correction costs one
  extra LLM call (+33%) and one web round trip, only on queries that need it.
  Latency was tried first and **failed as a measurement** — Groq's throttling
  swamps the route difference, and the first ordering produced a confounded
  result that looked convincing. That story is in RESULTS.md; it is the more
  useful half of this eval.

The exit code fails when missed fallbacks exceed the threshold, so a prompt or
model change that quietly breaks routing fails the way a test does.

## Tech Stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph (StateGraph) — conditional branching, corrective loops |
| LLM & embeddings | LangChain + Groq / FastEmbed / HuggingFace |
| Local knowledge base | ChromaDB / FAISS (cosine similarity) |
| Web search fallback | DuckDuckGo (default, no key) / Tavily (optional, `SEARCH_PROVIDER=tavily`) |
| Output validation | Custom LLM groundedness check + regex PII redaction |
| Backend | FastAPI (async ASGI) |
| Frontend | React + Vite + Tailwind CSS |
| Containerization | Docker & Docker Compose |

## How it works

1. **`retrieve`** — vector similarity search against ChromaDB for the top-k chunks.
2. **`grade_documents`** — an LLM binary grader scores whether the retrieved context is
   relevant/sufficient (`"yes"` / `"no"`).
3. **Relevant →** straight to `generate`.
4. **Not relevant →** `transform_query` rewrites the question into search-optimized
   keywords → `web_search_fallback` pulls fresh snippets → `generate`.
5. **`generate`** — synthesizes an answer grounded strictly in the verified context.
6. **`validate_guardrails`** — final scan: an independent LLM groundedness check plus PII
   redaction, before the answer is returned with a source badge (Local DB vs Web Fallback).

See [docs/TECHNICAL_SPEC.md](docs/TECHNICAL_SPEC.md) for the full architecture, state
schema, node contracts, and reference implementation. See
[docs/INTERVIEW_NOTES.md](docs/INTERVIEW_NOTES.md) for the pitch, USP deep-dives,
trade-offs, and anticipated Q&A.

## Project Structure

```
backend/    FastAPI app, LangGraph state machine, nodes, tools, guardrails
frontend/   React + Vite + Tailwind client (chat UI, source badges, trace viewer)
docs/       Setup guide, technical spec, build plan, roadmap, code notes, interview notes
```

## Setup

See [docs/SETUP.md](docs/SETUP.md) for the full git/repo setup steps that were actually run.

Only `GROQ_API_KEY` is required — web search defaults to DuckDuckGo, which needs no key.

```bash
cp .env.example .env       # fill in GROQ_API_KEY
docker compose up --build
```

- Frontend → <http://localhost:3001>
- Backend docs → <http://localhost:8001/docs>

Ports are 3001/8001 rather than 3000/8000 because other projects on this machine hold
those; override with `FRONTEND_PORT` / `BACKEND_PORT` in `.env`.

**First run:** the Chroma index is built into the image at `backend/vectorstore`, but if
it's empty, populate it with `.\dev.ps1 ingest`.

### Backend-only dev loop

`dev.ps1` runs everything in the backend container with the source bind-mounted, so edits
don't need a rebuild:

```powershell
.\dev.ps1 build              # only when requirements.txt changes
.\dev.ps1 ingest [-Reset]    # embed backend/data/ into Chroma
.\dev.ps1 ask "why does chunk overlap matter?"
.\dev.ps1 test               # 27 tests
.\dev.ps1 serve -Port 8042   # FastAPI alone
```

## Build Plan

See [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md) — session-wise schedule, who does what, timeline.

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md). Short version:

- **Phase 1** — Vector store ingestion + Chroma persistence + config
- **Phase 2** — LangGraph skeleton: `CRAGState`, nodes, conditional edges
- **Phase 3** — Grading + `transform_query` + web-search fallback
- **Phase 4** — Output validation layer (groundedness + PII)
- **Phase 5** — FastAPI `/api/query` endpoint with step logs
- **Phase 6** — React + Vite + Tailwind demo UI (source badges, trace viewer)
- **Phase 7** — Docker Compose + deployment

## Positioning

Part of an **"Agentic Self-Correcting Systems"** portfolio theme alongside the
Self-Healing SQL Agent — same architectural pattern (LLM + self-verification +
autonomous correction), applied to a different domain (retrieval relevance vs
SQL execution errors).
