# Roadmap — Interview-Ready Project Plan

**Goal:** Adaptive CRAG ko ek **interview me dikhane layak, depth-wala project** banana hai
(full production product nahi). Priority sirf un cheezon pe hai jo interview me "impressive"
aur "defendable" lagengi — agentic routing, self-verification, autonomous correction.

---

## Current Status (jo ban chuka hai)

**Phase 1–10 ✅ — poora stack chalta hai, dono corpora pe measured. Deployment baaki.**

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
- ✅ **Phase 8 — eval harness ban gaya** (`backend/eval/`, `.\dev.ps1 eval`). 20 labelled
  queries, routing **20/20**, **0 missed fallbacks**, groundedness 90–95%, aur per-route
  LLM call count (local 3.0 vs web 4.0). Poora analysis
  [backend/eval/RESULTS.md](../backend/eval/RESULTS.md) me.
  **Do cheezein jo eval ne pakdi:**
  1. Latency comparison **confounded tha** — cases file order me chal rahe the (pehle
     saare local, phir saare web), aur Groq ki throttling case 5 ke baad shuru hoti hai,
     to poora slowdown local bucket me gira. `interleave()` default kiya. Phir bhi
     latency route ka signal nahi deti — isliye cost argument ab **call counts** pe khada
     hai, jo exact hai.
  2. Groundedness checker ka ek **consistent false positive** (case #1) — answer verbatim
     corpus se hai phir bhi flag hota hai, teeno runs me.
  ⚠️ 100% ka matlab "router perfect hai" nahi, "labelled task aasan hai" hai — corpus gap
  categorical hai. RESULTS.md me likha hai ki eval ko sach me hard kaise banaya jaaye.
- ✅ **Test suite** — `backend/tests/`, 60 tests, `.\dev.ps1 test`. Dono routes, docs-replace
  invariant, search failure, guardrails ke saare case, aur API shape covered
- ✅ **Phase 6** — React + Vite + Tailwind **dashboard**: `Sidebar` nav jo chaar full-page
  views switch karta hai (Chat · Documents · Evaluation · System), `Message` (source badge +
  rewrite note + citations + **inline trace**), `TraceTimeline` (node-by-node, "Web search
  (skipped)" bhi dikhta hai taaki fallback ka conditional hona saaf rahe). App code me
  hamesha relative `/api/...` — dev me Vite proxy, prod me Nginx, koi hardcoded backend URL
  nahi. View URL hash me rehta hai (`#eval`), isliye refresh aur back button dono chalte hain.
  **UI me jaan-boojh ke jo nahi hai:** koi fake "0.92 relevance score" (grader binary hai)
  aur koi per-step timestamp (backend emit nahi karta) — detail CODE_NOTES me
- ✅ **UI trim** — ek right rail aur chaar stat cards **nikaal diye**. Rail wahi cheezein
  dobara bol raha tha jo `Message` dikhata hai aur sirf aakhri answer ki dikhata tha; stat
  cards har view pe repeat ho rahe the. Evaluation page nau metric cards se chaar
  measurement + do **evidence blocks** (asli table ke saath) pe aaya, aur usme "Who labelled
  this set" add hua — kyunki "measured on a labelled set" ke baad pehla sawaal yahi hai.
  **Sab kuch corpus-aware hai:** demo questions, findings, labelling note aur corpus note
  `CORPUS` ke hisaab se badalte hain, warna SciFact pe UI apne hi numbers ke khilaf bolta
- ✅ **`GET /api/stats`** — corpus counts + `eval/results.json` ke numbers + live config.
  Koi LLM call nahi, kyunki dashboard har page load pe ise hit karta hai
- ✅ **Phase 7** — `docker-compose.yml`: backend + frontend, Chroma volume, healthcheck,
  Nginx `/api/` proxy. Verified: `docker compose up` ke turant baad pehli query kaam karti hai
- ✅ **Phase 10 — doosra corpus (BEIR SciFact)**, `CORPUS` env se switch. `app/tools/beir_loader.py`
  (download + qrels), `eval/build_scifact_scenarios.py` (labels **dataset se**, mere likhe hue
  nahi), `eval/CORPORA.md`. Naya metric: **`recall@k`** — gold doc retrieve hua ya nahi, jo
  concepts corpus pe possible hi nahi tha (koi ground truth nahi thi). Dono corpora alag
  Chroma collections me.
  **Teen bugs jo bada corpus laane pe hi mile:**
  1. **OOM ×2** (exit 137) — 17,266 chunks 3.5 GB me nahi aaye. Ingestion ab **stream** karti
     hai (per-batch split → embed → chhod do), peak memory corpus size se azaad.
  2. **SQLite lock contention** — `docker compose` ka backend wahi `vectorstore/` mount kiye
     baitha tha; ingest 5 min block rahi **bina kisi error ke**, bas hang. Bada ingest chalane
     se pehle compose band karna padta hai.
  3. **`--limit` truncation nahi ho sakta** — gold docs cut ho jaate aur phir eval me wo
     failure *grader ki galti* jaisa dikhta, jabki galti corpus ki hoti. Ab gold docs pehle,
     phir filler. `test_corpus.py` assert karta hai
- ✅ **SciFact pe A/B chal gaya** (500 docs → 1,717 chunks). Baseline vs hybrid+rerank:
  routing **75.0% → 78.6%**, recall@k **65% → 70%**, unnecessary fallbacks 7 → 6,
  missed fallbacks dono me **0**.
  - **Sirf ek case badla** (#10: gold `MISS → hit`, route `web → local`) — 20 cases pe
    +5pp matlab ek document, yaani noise ke andar. Jo establish hua wo **mechanism** hai,
    magnitude nahi.
  - **Isse bada finding:** baseline pe gold doc mila to 13/13 sahi route, miss hua to
    7/7 web. **Grader ne ek bhi apni galti nahi ki** — saare "routing failures" retrieval
    misses the jinhe usne theek pakda. Matlab 75% grader ko under-report karti hai, aur
    bottleneck **retrieval** hai, grading nahi.
- ❌ Deployment — abhi nahi hua. Render free tier naap ke **reject** kiya (peak 464 MB
  vs 512 MB limit, persistent disk nahi, sleep hota hai); target HuggingFace Spaces hai.
  Poora plan aur teen prerequisites neeche "Deployment Plan" me
- ❌ Poora 5k corpus + 300-query test set — laptop ki Docker memory (3.5 GB) me nahi aata.
  Reranking sach me kaam karta hai ya nahi, wo isi pe pata chalega

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
Dashboard: nav rail, chat with source badges + citations, aur har answer ke neeche inline
trace / system config / eval numbers. Live demo Swagger se hamesha better lagta hai.

### Phase 7 — Docker Compose + Deployment
`backend` + `frontend` services, `/api/` proxy, Chroma persistence volume. Deploy **abhi nahi
hua**; plan neeche "Deployment Plan (free tier)" me hai — Render + Vercel naap ke reject kiya,
target ek HuggingFace Space hai jisme dono ek hi image me chalte hain.

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

**Pehla plan Render + Vercel tha. Naapne ke baad wo hata diya — Render free tier me ye
app fit nahi hoti.** Ye guess nahi hai; `docker stats` se liye gaye numbers hain, concepts
corpus (22 chunks) pe:

| | Memory |
|---|---|
| Backend idle, boot ke baad | 266 MB |
| Ek local query ke baad (hybrid + reranker load ho chuke) | 457 MB |
| Ek web query ke baad (peak) | **464 MB** |
| Backend image | 1.32 GB |
| Frontend image | 102 MB |
| Vectorstore on disk | 12 MB |

Render free = **512 MB**, yaani **48 MB headroom** — ek bhi concurrent request pe OOM.
Aur ye sabse chhote corpus ka number hai; SciFact (1,717 chunks) isse upar jaata hai.
Do aur cheezein Render free pe todti hain: **persistent disk nahi hota** (to Chroma volume
mount ho hi nahi sakta), aur 15 min baad **sleep** ho jaata hai. Paid se bhi fayda nahi —
Render ka $7 wala tier bhi 512 MB hi hai; 2 GB $25/mo pe aata hai.

### "Reranker band karke Render me fit kar do" — naapa, aur reject kiya

Ye obvious sawaal hai, isliye iska number bhi naapa hua hai:

| Config | idle | local query | web query (peak) |
|---|---|---|---|
| Hybrid + reranker **on** (asli pipeline) | 266 MB | 457 MB | **464 MB** |
| Hybrid + reranker **off** | 74 MB | 242 MB | **250 MB** |

Flags off karke 512 MB me aaram se fit ho jaata hai — cross-encoder aur BM25 index
milke ~214 MB lete hain. **Phir bhi ye raasta nahi liya.**

Wajah: System Status page tab likhega *"Hybrid: off, Cross-encoder rerank: off"*, jabki
Evaluation page ka poora A/B usi pipeline ke baare me hai. Live demo wo cheez chala hi
nahi raha hoga jiska measurement dikhaya ja raha hai — aur dashboard ka apna usool hai ki
screen pe koi aisi baat na ho jo backend se match na karti ho. Chhote dabbe me ghusne ke
liye sabse acha kaam band kar dena ulta sauda hai.

**Isliye target: [HuggingFace Spaces](https://huggingface.co/spaces)** — 16 GB RAM free,
Docker support, aur ek ML demo ka natural ghar hai.

| Piece | Kahan | Kyun |
|---|---|---|
| Poora stack (ek image) | HuggingFace Spaces (Docker SDK) | 16 GB RAM, persistent, sleep nahi |
| Vector DB | Chroma — **image me bake karke** | 12 MB hai; volume ki zaroorat hi nahi |
| LLM | [Groq](https://console.groq.com) | Free, fast. Key HF **Secrets** me |
| Web search | DuckDuckGo (default) — koi key nahi | Signup ke bina chalta hai |

### Karne se pehle teen kaam

1. **Backend + frontend ko ek image me merge karo.** Nginx static build serve kare aur
   `/api/` backend pe proxy kare — wahi jo abhi compose me ho raha hai. Isse **CORS ki
   zaroorat hi khatam** ho jaati hai, kyunki origin ek hi rehta hai.
2. **CORS band karo** — `backend/main.py:42` pe `allow_origins=["*"]` hai aur TODO pada
   hai. Step 1 ke baad ise apne origin tak seemit karo.
3. **Vectorstore image me bake karo** — `backend/vectorstore` 12 MB ka hai, `.dockerignore`
   se nikaal do taaki COPY ho jaaye. Warna Space har restart pe khaali index se boot hoga.

**Gotchas:**
- Groq rate limits — demo ke liye fixed queries (UI ke chips).
- **`.env` kabhi commit mat karna — aur `.env.example` me kabhi asli key mat daalna.** Wo
  file commit hoti hai. HF pe key **Settings → Secrets** me jaati hai, Dockerfile me nahi.
- Embedding aur reranker model pehli baar download hote hain — Docker layer me cache karo,
  warna har cold start pe download hoga.

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
