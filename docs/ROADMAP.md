# Roadmap — Interview-Ready Project Plan

**Goal:** Adaptive CRAG ko ek **interview me dikhane layak, depth-wala project** banana hai
(full production product nahi). Priority sirf un cheezon pe hai jo interview me "impressive"
aur "defendable" lagengi — agentic routing, self-verification, autonomous correction.

---

## Current Status (jo ban chuka hai)

**Phase 1–7 ✅ — poora stack `docker compose up` se chalta hai. Eval harness abhi baaki.**

- ✅ Repo scaffold + docs (README, TECHNICAL_SPEC, SETUP, BUILD_PLAN, ROADMAP, CODE_NOTES, INTERVIEW_NOTES)
- ✅ **Phase 1** — `requirements.txt`; `app/config.py` (`Settings` + `get_llm` / `get_embeddings` /
  `get_vectorstore` factories); `app/tools/vector_search.py`; `backend/data/` — 7-doc controlled
  corpus **with a deliberate gap**; `ingest.py` (idempotent, `--reset`); `backend/Dockerfile`
- ✅ **Phase 2** — `app/schemas/crag_state.py` (`CRAGState`, additive `logs` reducer);
  `app/graph/state.py`; `app/nodes/retrieve.py`; `app/nodes/generate.py`;
  `app/graph/build_graph.py` (`START → retrieve → generate → END`); `app/__main__.py` CLI
- ✅ `dev.ps1` — Docker dev loop (is machine pe local Python installed nahi hai)
- ✅ **Verified:** ingestion chali (7 docs → 22 chunks persisted); retrieval sahi chunks laati hai;
  graph compile hota hai, node order + `logs` reducer sahi merge karte hain
- ✅ **Phase 3 (asli USP)** — `app/nodes/grade_documents.py` (binary grader + defensive
  `parse_verdict`), `app/nodes/transform_query.py`, `app/tools/tavily_search.py`,
  `app/nodes/web_search_fallback.py`, aur `build_graph.py` me `decide_to_generate`
  conditional edge
- ✅ **Verified (mocked LLM + mocked Tavily):** happy path `retrieve → grade:yes → generate`
  (`source=vector_db`); correction path `retrieve → grade:no → transform → web → generate`
  (`source=web_search`, local docs **replace** hue — merge nahi); Tavily failure pe graph
  crash nahi karta, `generate` saaf bolta hai ki context nahi mila; `parse_verdict` ke 10 cases
- ✅ **Search provider abstraction** — `app/tools/web_search.py` + `duckduckgo_search.py`.
  **Default DuckDuckGo, koi API key nahi chahiye.** Tavily ab optional upgrade hai
  (`SEARCH_PROVIDER=tavily`)
- ✅ **Phase 4** — `app/guardrails/validators.py` (LLM groundedness + regex PII) +
  `app/nodes/validate_guardrails.py`. **`guardrails-ai` library nahi li** — ROADMAP me jo
  fallback plan likha tha wahi liya (zero dependency, same interview point)
- ✅ **Phase 5** — `main.py`: `POST /api/query` (answer + source_type + relevance_score +
  transformed_query + logs + elapsed_ms), `GET /health`, CORS, `run_in_threadpool`
- ✅ **Verified:** correction path pe **asli DuckDuckGo search** chali (real MCP snippets aaye,
  bina kisi key ke); guardrails ke chaaron case (clean / ungrounded→flag / PII→redact /
  check-down→fail-open); API pe asli HTTP requests — `/health` ok, khaali question `422`,
  bina key ke query `500` saaf error message ke saath
- ✅ **ASLI END-TO-END RUN HO GAYA** — Groq (`openai/gpt-oss-120b`) + live DuckDuckGo.
  `data/README.md` ki **paanchon fixed demo queries sahi route leti hain** (3 local, 2 web).
  Happy path: `grade:yes → generate`, `source=vector_db`. Correction path: `grade:no →
  transform → web → generate`, `source=web_search`, asli MCP snippets. Guardrails dono pe
  `pass=True (clean)`
- ⚠️ **Model badalna pada:** `llama-3.3-70b-versatile` is Groq account pe available nahi hai
  (404 `model_not_found`). `/v1/models` list karke `openai/gpt-oss-120b` pe switch kiya —
  yahi wo cheez hai jo mocks kabhi nahi pakadte
- 🟡 **Abhi bhi pending:** eval harness. Routing 5/5 sahi aayi, par ye ek chhota controlled
  set hai — koi accuracy percentage claim karne layak data abhi nahi hai
- ✅ **Test suite** — `backend/tests/`, 27 tests, `.\dev.ps1 test`. Dono routes, docs-replace
  invariant, search failure, guardrails ke saare case, aur API shape covered
- ✅ **Phase 6** — React + Vite + Tailwind UI: `ChatBox` (fixed demo queries ke saath),
  `SourceBadge`, `RelevancePill`, `TraceViewer` (node-by-node timeline). App code me hamesha
  relative `/api/...` — dev me Vite proxy, prod me Nginx, koi hardcoded backend URL nahi
- ✅ **Phase 7** — `docker-compose.yml`: backend + frontend, Chroma volume, healthcheck,
  Nginx `/api/` proxy. Verified: `docker compose up` ke turant baad pehli query kaam karti hai
- ❌ Deployment (Render + Vercel) — abhi nahi hua

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

### Phase 4 — Output Validation ✅
`validators.py` — **custom** LLM groundedness check + regex PII redaction. `validate_guardrails`
node final answer scan karta hai before return.

**Jo plan tha vs jo hua:** Guardrails AI library plan me thi, li nahi gayi — hub download +
version pinning time-sink tha. ROADMAP me jo fallback plan likha tha (simple LLM groundedness
check) wahi liya gaya. Zero extra dependency, same interview point.

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
| Web search | DuckDuckGo (default) — koi key nahi. [Tavily](https://tavily.com) optional | Signup ke bina chalta hai |
| Frontend | [Vercel](https://vercel.com) / [Netlify](https://netlify.com) | Free static, GitHub auto-deploy |

**Gotchas:**
- Render free tier sleep hota hai — demo se pehle URL warm kar lena.
- Groq rate limits — demo ke liye fixed queries (`backend/data/README.md`).
- **`.env` kabhi commit mat karna — aur `.env.example` me kabhi asli key mat daalna.** Wo
  file commit hoti hai.
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
