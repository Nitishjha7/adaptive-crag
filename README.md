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
> | Test suite — 27 tests (`.\dev.ps1 test`) | ✅ |
> | Phase 6 — frontend demo UI | ❌ not written (CLI and Swagger only) |
> | Phase 7 — `docker-compose.yml` | ❌ still empty |
> | Evaluation harness | ❌ **no accuracy has been measured** |
>
> Routing was correct on all five demo queries, but that is a small controlled set, not a
> benchmark — don't quote an accuracy figure until the eval harness in
> [docs/ROADMAP.md](docs/ROADMAP.md) exists.

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

`docker-compose.yml` is still empty (Phase 7). Until then, use `dev.ps1`, which runs
everything in the backend container with the source bind-mounted:

```powershell
copy .env.example .env    # fill in GROQ_API_KEY; TAVILY_API_KEY is optional
.\dev.ps1 build           # build the image (only needed when requirements change)
.\dev.ps1 ingest          # embed backend/data/ into Chroma
.\dev.ps1 ask "why does chunk overlap matter?"
.\dev.ps1 serve           # FastAPI on http://localhost:8000/docs
```

Only `GROQ_API_KEY` is required — web search defaults to DuckDuckGo, which needs no key.

Backend: `POST /api/query` → answer + `source_type` + `relevance_score` + step execution
logs. Frontend (Phase 6, not built) will show source badges and the LangGraph trace.

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
