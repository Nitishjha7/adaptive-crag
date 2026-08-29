# Adaptive Corrective RAG (CRAG) with Web Search Fallback

An agentic RAG system built with LangGraph that self-grades retrieved documents,
rewrites ambiguous queries, and falls back to live web search when local context is
insufficient — eliminating hallucinations from stale or irrelevant vector-store hits.

Naive RAG blindly trusts whatever the vector DB returns. CRAG adds a verification loop:
a grading node decides whether the retrieved chunks actually answer the question, and only
falls back to the web when they don't — so you get grounded answers without paying the
cost and latency of a web call on every query.

## Tech Stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph (StateGraph) — conditional branching, corrective loops |
| LLM & embeddings | LangChain + Groq / FastEmbed / HuggingFace |
| Local knowledge base | ChromaDB / FAISS (cosine similarity) |
| Web search fallback | Tavily Search API / DuckDuckGo Search |
| Output validation | Guardrails AI (hallucination / PII / toxicity) |
| Backend | FastAPI (async ASGI) |
| Frontend | React + Vite + Tailwind CSS |
| Containerization | Docker & Docker Compose |

## How it works

1. **`retrieve`** — vector similarity search against ChromaDB for the top-k chunks.
2. **`grade_documents`** — an LLM binary grader scores whether the retrieved context is
   relevant/sufficient (`"yes"` / `"no"`).
3. **Relevant →** straight to `generate`.
4. **Not relevant →** `transform_query` rewrites the question into search-optimized
   keywords → `web_search_fallback` (Tavily) pulls fresh snippets → `generate`.
5. **`generate`** — synthesizes an answer grounded strictly in the verified context.
6. **`validate_guardrails`** — final scan for hallucination, PII leakage, and toxic
   content before the answer is returned, with a source badge (Local DB vs Web Fallback).

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

```bash
cp .env.example .env   # fill in GROQ_API_KEY and TAVILY_API_KEY
docker compose up --build
```

Backend: `POST /api/query` → answer + `source_type` + step execution logs.
Frontend: served via Nginx, shows source badges (Local DB vs Web Fallback) and the
LangGraph execution trace.

## Build Plan

See [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md) — session-wise schedule, who does what, timeline.

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md). Short version:

- **Phase 1** — Vector store ingestion + Chroma persistence + config
- **Phase 2** — LangGraph skeleton: `CRAGState`, nodes, conditional edges
- **Phase 3** — Grading + `transform_query` + Tavily web-search fallback
- **Phase 4** — Guardrails AI output validation layer
- **Phase 5** — FastAPI `/api/query` endpoint with step logs
- **Phase 6** — React + Vite + Tailwind demo UI (source badges, trace viewer)
- **Phase 7** — Docker Compose + deployment

## Positioning

Part of an **"Agentic Self-Correcting Systems"** portfolio theme alongside the
Self-Healing SQL Agent — same architectural pattern (LLM + self-verification +
autonomous correction), applied to a different domain (retrieval relevance vs
SQL execution errors).
