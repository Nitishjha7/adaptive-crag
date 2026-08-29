# Roadmap — Interview-Ready Project Plan

**Goal:** Adaptive CRAG ko ek **interview me dikhane layak, depth-wala project** banana hai
(full production product nahi). Priority sirf un cheezon pe hai jo interview me "impressive"
aur "defendable" lagengi — agentic routing, self-verification, autonomous correction.

---

## Current Status (jo ban chuka hai)

- ✅ Repo scaffold — `backend/`, `frontend/`, `docs/`, `docker-compose.yml`, `.gitignore`, `.env.example`
- ✅ Empty placeholder files: `state.py`, `build_graph.py`, `retrieve.py`,
  `grade_documents.py`, `transform_query.py`, `web_search_fallback.py`, `generate.py`,
  `validate_guardrails.py`, `tavily_search.py`, `vector_search.py`, `validators.py`, `main.py`
- ✅ Docs: README, TECHNICAL_SPEC, SETUP, BUILD_PLAN, ROADMAP, CODE_NOTES, INTERVIEW_NOTES
- ❌ Koi actual implementation nahi (sab files khaali hai)
- ❌ Vector store ingestion
- ❌ Frontend

---

## Phase Order

### Phase 1 — Vector Store Ingestion & Config
Local documents ko ChromaDB collection me ingest karna FastEmbed embeddings se, Docker
volume pe persist. `config.py` me LLM (Groq via LangChain) + embedding factory,
`pydantic-settings` se `.env` load.

**Kyun pehle:** baaki sab isi pe khada hai. Controlled dataset (5–10 docs, ek deliberate
"gap") ingest karna taaki fallback predictably trigger ho demo me.

### Phase 2 — LangGraph Skeleton
`CRAGState` TypedDict (additive reducers for `documents` + `logs`), `StateGraph` with
`retrieve` → `generate` and `START`/`END` wiring. Ek dummy query end-to-end chale.

**Interview point:** "chain kyun nahi, graph kyun" — mujhe conditional branching chahiye,
runtime pe decide ki kaunsa path lena hai. State object pura execution trace maintain karta hai.

### Phase 3 — Grading, Query Transform & Web Fallback
- `grade_documents` — LLM binary grader ("yes"/"no" relevance), defensive parse.
- Conditional edge — `yes` → `generate`, `no` → `transform_query`.
- `transform_query` — natural language → keyword-focused web query.
- `tavily_search` tool + `web_search_fallback` node — `documents` replace, `source_type = "web_search"`.

**Interview point:** "web search hamesha kyun nahi" — cost + latency; local hit fast hai,
fallback sirf zaroorat pe. Yahi "Adaptive" ka matlab hai.

### Phase 4 — Guardrails Output Validation
`validators.py` — Guardrails AI se groundedness / PII / toxicity check. `validate_guardrails`
node final answer scan karta hai before return. Agar Guardrails AI heavy lage toh custom
LLM groundedness check fallback.

**Interview point:** "guardrails kyun" — LLM apni training knowledge se kuch add na kare;
answer sirf verified context se grounded ho.

### Phase 5 — FastAPI Endpoint
`POST /api/query` — question in, `{answer, source_type, relevance_score, logs}` out.
Step execution logs response me — explainability ke liye. `/health` for Docker.

### Phase 6 — Frontend Demo UI (React + Vite + Tailwind)
`ChatBox`, `SourceBadge` (Local DB / Web Fallback), `TraceViewer` (kaunsa node chala kis
order me), `RelevancePill` (yes/no). Live demo Swagger se hamesha better lagta hai.

### Phase 7 — Docker Compose + Deployment
`backend` + `frontend` services, `/api/` proxy, Chroma persistence volume. Deploy: Render
(backend) + Vercel (frontend).

---

## Aage ki priority (proof-of-work — interview me strong)

### A. Evaluation / metrics script
`eval/scenarios.json` — 15–20 queries with expected route (`local` / `web`) aur expected
answer keywords. Ek script measure kare: grading accuracy, fallback precision (kya sach me
tabhi web gaya jab local insufficient tha), groundedness rate.

**Kyun:** "bana ke chhod diya" vs "maine measure kiya" — interviewer turant pakadta hai.
Numbers strong hote hain.

### B. Demo dataset + recorded walkthrough
Chhota controlled doc set + 3 fixed demo queries (happy path, correction path, guardrail
catch). Trace logs ka screenshot portfolio ke liye.

### C. `docs/INTERVIEW_NOTES.md` — ✅ already likha hua
30-sec pitch, problem, tech stack rationale, full flow, USP deep-dives, limitations +
mitigations, presentation script, anticipated Q&A. Jaise-jaise implementation aage badhe,
concrete numbers (measured grading accuracy, fallback precision) add karte rehna.

---

## Deployment Plan (free tier)

| Piece | Kahan | Kyun |
|---|---|---|
| Backend (FastAPI) | [Render](https://render.com) / [Railway](https://railway.app) | Docker deploy, free tier |
| Vector DB | Chroma persistent volume / [Chroma Cloud](https://www.trychroma.com) | Local persistence kaafi hai |
| LLM | [Groq](https://console.groq.com) | Free, very fast inference |
| Web search | [Tavily](https://tavily.com) | Free tier ~1000 searches/month |
| Frontend | [Vercel](https://vercel.com) / [Netlify](https://netlify.com) | Free static, GitHub auto-deploy |

**Gotchas:**
- Render free tier sleep hota hai — demo se pehle URL warm kar lena.
- Groq / Tavily rate limits — demo ke liye fixed queries.
- `.env` kabhi commit mat karna — sirf `.env.example`.
- Embedding model pehli baar download hota hai — Docker layer me cache.

---

## Order of Execution

1. Phase 1 — vector store + config
2. Phase 2 — LangGraph skeleton
3. Phase 3 — grading + transform + web fallback
4. Phase 4 — guardrails
5. Phase 5 — FastAPI endpoint
6. Phase 6 — frontend demo UI
7. Phase 7 — Docker Compose + deployment
8. Evaluation script
9. `docs/INTERVIEW_NOTES.md` refine — real measured numbers bharna
