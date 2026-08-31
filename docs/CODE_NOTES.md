# Code Notes — Kya Kis Liye Hai

Ye file har file / dependency ka **kaam aur reason** track karti hai, taaki baad me (ya
interview me) yaad rahe ki har cheez kyun li gayi.

**Legend:** ✅ = likha ja chuka · ⬜ = abhi khaali (planned intent).
Phase 1–5 ✅ ho chuke; Phase 6 (frontend) + 7 (compose) ⬜.

---

## backend/requirements.txt ✅

| Package | Kya kaam karta hai | Kyun liya |
|---|---|---|
| `langgraph` | Stateful agent graph — nodes + conditional edges | CRAG ka core. Simple chain se conditional branching (relevant → generate, warna → fallback) express nahi hota; graph chahiye |
| `langchain` / `langchain-core` | LLM abstractions, prompt templates, output parsers | Grader / rewrite / generate sab prompt chains hain. Provider swap karna easy |
| `langchain-groq` | Groq LLM binding | Free tier + bahut fast inference — grading jaisa chhota call latency-sensitive hai |
| `chromadb` | Embedded vector database | Local knowledge base. Zero infra (embedded), Docker volume pe persist ho jaata hai |
| `fastembed` | Lightweight local embedding models (ONNX) | API key nahi chahiye, offline chalta hai, fast. HuggingFace se halka |
| `tavily-python` | Tavily Search API client | **Optional upgrade** (`SEARCH_PROVIDER=tavily`). LLM-optimized snippets deta hai (raw HTML nahi), par signup chahiye |
| ~~`guardrails-ai`~~ | — | **Nahi liya.** Hub download + version pinning time-sink tha; custom LLM groundedness check + regex PII usi kaam ko zero dependency me karta hai. Neeche `validators.py` dekh |
| `ddgs` | DuckDuckGo search client | **Default web search provider — koi API key nahi chahiye.** Project pehle din se chalta hai |
| `fastapi` | ASGI web framework — REST endpoint | `/api/query` gateway. Async-native, auto `/docs` |
| `uvicorn[standard]` | ASGI server jo FastAPI run karta hai | FastAPI khud server nahi hai |
| `pydantic` / `pydantic-settings` | Validation + typed config | Request/response models; `.env` se typed settings |
| `python-dotenv` | `.env` load (dev) | Local dev me env vars |

---

> `langchain-text-splitters` bhi add hua — `RecursiveCharacterTextSplitter` ingestion me
> chahiye tha (paragraph/heading boundaries pe todta hai, fixed character count pe nahi).

---

## backend/app/config.py ✅

Central config + factory functions. Koi business logic nahi.

- `Settings(BaseSettings)` — `GROQ_API_KEY`, `TAVILY_API_KEY`, model names, `TOP_K`,
  chunk params, paths. `.env` repo root se load hoti hai (docker-compose bhi wahi padhta hai).
- `get_llm(temperature=0.0)` — configured `ChatGroq`. Key missing ho to saaf error message.
- `get_embeddings()` — `FastEmbedEmbeddings` (local ONNX, koi API call nahi).
- `get_vectorstore()` — persisted Chroma collection ka handle.

**Kyun factory, direct import nahi:** test me mock karna easy (Phase 2 ka wiring test
`get_llm` ko fake se replace karke hi chala tha, bina Groq key ke), aur model swap ek jagah se.

**Kyun `@lru_cache`:** har node config import karta hai. Bina cache ke har call pe `.env`
dobara parse hota aur naya embedding model load hota — slow aur bewajah.

**`ChatGroq` / `FastEmbedEmbeddings` ka import function ke andar kyun hai:** module import
sasta rehta hai. `python -m app --help` jaisa kuch chalane pe heavy ML deps load nahi hote.

---

## backend/data/ ✅ — controlled corpus

7 markdown docs — RAG / agent engineering **concepts** (embeddings, chunking, vector DBs,
naive-RAG failure modes, CRAG, query transformation, agent graphs & state).

**Deliberate gap:** koi product/pricing/vendor detail nahi, koi recent release nahi, aur
**MCP ka zero mention**. Ye gap hi Scenario 2 (correction path) ko predictably trigger karta
hai — demo live randomness pe depend nahi karta.

**Corpus real topics ka kyun, fictional company ka kyun nahi:** fictional hota to `grade: no`
to aa jaata, lekin web search bhi kachra deta aur demo ka doosra half mar jaata. Gap aisa
chahiye jo web se **genuinely answerable** ho.

Fixed demo queries + expected routes `backend/data/README.md` me hai.

---

## backend/ingest.py ✅

Docs → chunks → embeddings → Chroma.

- `load_documents()` — `data/*.md|txt` padhta hai, `README.md` skip karta hai (wo corpus ka
  part nahi; usko ingest karna corpus me "yahan kya nahi hai" wala meta-text daal deta, jo
  grader ko confuse karta).
- `split_documents()` — `RecursiveCharacterTextSplitter`, 800/100, separators me `\n## ` sabse
  pehle taaki heading boundaries pe toote.
- **Idempotent** — collection bhari ho to skip. `--reset` se wipe + rebuild.

**Ek real bug jo yahan mila:** `--reset` pehle `shutil.rmtree(store_dir)` karta tha. Docker me
`vectorstore/` ek **mount point** hai, aur usko remove karne pe `OSError: Device or resource
busy` aata hai. Fix: directory nahi, uske **contents** clear karo.

---

## backend/app/__main__.py ✅

`python -m app "question"` — graph ko FastAPI ke bina invoke karke poora trace print karta hai.
API ban chuki hai, phir bhi debugging ka sabse chhota loop yahi hai: ek process, ek invoke, poora trace.

---

## dev.ps1 ✅ (repo root)

Is machine pe local Python installed nahi hai — sab kuch Docker me chalta hai. Ye helper
lamba `docker run` incantation wrap karta hai: `build` / `ingest [-Reset]` / `ask "..."` /
`test` / `serve [-Port N]` / `shell`.

Code **bind-mount** hota hai (`app/`, `data/`, `ingest.py`), isliye edit ke baad rebuild nahi
karna padta — image sirf dependencies deti hai. `.env` `--env-file` se inject hoti hai, image
me bake nahi hoti.

Phase 7 me proper `docker-compose.yml` isko replace kar dega.

---

## backend/tests/ ✅ — 27 tests, `.\dev.ps1 test`

| File | Kya cover karta hai |
|---|---|
| `conftest.py` | `fake_llm` aur `fake_search` fixtures (monkeypatch se, taaki test ke baad apne aap undo ho) |
| `test_routing.py` | dono routes, docs replace hona, search failure, ajeeb grader output |
| `test_grading.py` | `parse_verdict` ke 11 cases |
| `test_validation.py` | PII redaction, false positives, ungrounded flagging, fail-open |
| `test_api.py` | `/health`, 422 validation, response shape |

**Tests me asli LLM call kyun nahi:** ye **control flow** ke test hain, model quality ke
nahi. Asli calls slow, mehnge, key-dependent aur non-deterministic hote — yaani CI me flaky.
Grader ko scripted verdict dena hi wo cheez hai jo test karni hai: *"agar grader 'no' bole
to kya graph sahi raasta leta hai."* Grader ki **accuracy** alag cheez hai — wo eval harness
ka kaam hai (ROADMAP), in tests ka nahi.

**Sabse important test:** `test_fallback_replaces_local_docs_instead_of_merging`. Agar reject
kiye hue local docs web snippets ke saath context me bach gaye, to CRAG ka poora point khatam —
aur ye baat silently toot sakti hai, isliye assert kiya hua hai.

---

## backend/app/schemas/crag_state.py ✅

`CRAGState` TypedDict — graph ka single source of truth. Har node ise partially update karta hai.

- `question` — original, kabhi mutate nahi hota.
- `transformed_query` — sirf `transform_query` node set karta hai.
- `documents` — **overwrite** semantics (koi reducer nahi). `retrieve` set karta hai,
  `web_search_fallback` **replace** karta hai. Yahan additive reducer *deliberately nahi*
  lagaya: append karte to reject kiye hue local docs web snippets ke saath context me bane
  rehte — wahi hallucination risk jise grading step hatane ke liye hai.
- `relevance_score` — `"yes"` / `"no"`, conditional edge isi pe route karta hai.
- `source_type` — `"vector_db"` default, fallback pe `"web_search"`. UI badge isi se.
- `generation` — raw LLM answer.
- `final_output` — guardrails-validated answer, yahi user ko jaata hai.
- `logs` — har node ek line append karta hai (`Annotated[list, operator.add]`). Trace viewer isi se.

---

## backend/app/graph/build_graph.py ✅ (poora graph)

Graph wiring — nodes register, edges define, `compile()`.

### Abhi ka shape

- `START → retrieve → grade_documents`.
- `grade_documents` pe conditional edge: `relevance_score == "yes"` → `generate`, warna
  → `transform_query`.
- `transform_query → web_search_fallback → generate`.
- `generate → validate_guardrails → END`.

**Chain kyun nahi, graph kyun — ab saaf dikhta hai:** `grade_documents` ke baad kaunsa node
chalega ye compile time pe fixed nahi hai; runtime pe state padh ke decide hota hai. Linear
chain ye express hi nahi kar sakti.

**`decide_to_generate` alag function kyun:** routing logic aur grading logic alag rakhne se
dono alag-alag test hote hain. Ye function deliberately trivial hai — saara faisla
`grade_documents` me hota hai, yahan sirf uska result padha jaata hai.

**Default `transform_query` kyun, `generate` nahi:** agar `relevance_score` kisi wajah se
khaali reh jaye, to safe direction correction path hai — ek extra web call bhugto, lekin
unverified context pe answer mat bolo.

**Design choice:** fallback branch bhi wapas `generate` pe hi merge hota hai (do alag
generate nodes nahi) — DRY, aur `generate` bas `state["documents"]` padhta hai, source
type se farak nahi padta.

---

## backend/app/nodes/retrieve.py ✅

`retrieve` node — Chroma se cosine similarity top-k chunks.

- `get_vectorstore().similarity_search(question, k=4)`.
- Chunks `documents` me append, `source_type = "vector_db"`.
- Log: `"retrieve -> k chunks"`.

---

## backend/app/nodes/grade_documents.py ✅

**Project ka core #1.** LLM binary relevance grader.

- Prompt tight rakha — "answer with a single word: yes/no, do not explain".
- Parse defensively: `"yes" in verdict.lower()` — LLM kabhi extra text de deta hai.
- Temperature 0 — consistency chahiye, creativity nahi.
- Sirf `relevance_score` + `logs` return karta hai.

**Interview point:** ye ek chhota, sasta classifier call hai — poore answer generate karne
se pehle. Yahi naive RAG se difference hai: verify-before-trust.

---

## backend/app/nodes/transform_query.py ✅

`transform_query` — natural language question → keyword-focused web search query.

- User question conversational hota hai ("mujhe ye samajhna hai ki...") — search engine ke
  liye keywords better hain.
- Rewritten query `transformed_query` me, `web_search_fallback` use karta hai.

---

## backend/app/nodes/web_search_fallback.py ✅

**Core #2.** Tavily se live web context.

- `transformed_query` (ya fallback pe original question) se `tavily_search(query, max_results=4)`.
- Result snippets se `documents` **replace** (local irrelevant tha, isliye rakhne ka fayda nahi).
- `source_type = "web_search"` — UI badge + logs.

**Kyun replace, merge nahi:** local docs already "no" grade ho chuke — unko context me
rakhna generation ko dilute karega aur hallucination risk badhayega.

---

## backend/app/nodes/generate.py ✅

`generate` — final answer synthesis.

- Prompt: "answer ONLY from the provided context; if context insufficient, say so".
- `state["documents"]` join karke context banata hai — local ya web, farak nahi.
- Output `generation` me (raw, abhi guardrails-checked nahi).

---

## backend/app/nodes/validate_guardrails.py ✅

`validate_guardrails` — graph ka aakhri safety net. `final_output` yahi node bharta hai.

- `guardrails/validators.py` ka `validate_answer(answer, context, question)` call.
- Log: `"validate_guardrails -> pass=True/False (reason)"`.

**Ye node kyun, jab `generate` ka prompt already "sirf context se" bolta hai:** prompt ek
guzarish hai, guarantee nahi. Model chupke se apni training knowledge daal sakta hai. Ye
node us answer par ek doosri, *independent* nazar hai.

---

## backend/app/guardrails/validators.py ✅ — custom, Guardrails AI **nahi**

> **Decision (Phase 4):** `guardrails-ai` library use *nahi* ki. Uska hub-based validator
> download + version pinning is project ka sabse bada time-sink tha, aur interview me jo
> matter karta hai wo library ka naam nahi — ye samajh hai ki final answer verify kyun aur
> kaise karna hai. Do chhote checks wahi kaam karte hain, zero extra dependency me.
> ROADMAP me ye fallback plan pehle se likha tha; wahi liya gaya.

Do checks:

1. **Groundedness (LLM call)** — "kya answer ka har claim context se supported hai? yes/no".
   Temperature 0, wahi defensive `parse_verdict` jo grader me hai (reuse — do jagah parsing
   logic drift na kare).
2. **PII (regex)** — email / card / SSN / intl phone. **Deliberately regex, LLM nahi:** PII
   detection deterministic honi chahiye, aur ek aur LLM call latency badhata hai bina
   bharose ke faayde ke.

**Toxicity chhoda kyun:** input controlled corpus + search snippets hai, aur bina proper
classifier ke "toxic" ka LLM check dikhawa hota. Uska naam lena aur verify na karna — dono
me se naam *na* lena behtar hai.

### Do design decisions jo interview me poochhe ja sakte hain

**Ungrounded answer block nahi hota, flag hota hai.** Warning prefix jodte hain, answer
chhupate nahi. Demo me hallucination *pakda gaya* dikhana usse gayab kar dene se zyada
convincing hai — aur user ke liye bhi "ye shayad galat hai" khaali screen se behtar hai.
**PII isse alag hai** — wo redact hota hai, kyunki flag karke dikhana leak hi hai.

**Groundedness check fail-open hai, fail-closed nahi.** Agar check khud crash ho jaye
(network / rate limit), answer block karna galat hai — wo already verified context se bana
hai. Exception pe "grounded maan lo" + log me note. Fail-closed hone se ek flaky call poore
system ko "kuch nahi bata sakta" bana deta.

---

## backend/app/tools/web_search.py ✅ — provider abstraction

`web_search_fallback` node yahin se search karta hai; usse pata nahi hota ki neeche kaun
hai. Provider `SEARCH_PROVIDER` env var se badalta hai, code se nahi.

**Ye layer kyun:** DuckDuckGo bina key ke chalta hai (project din ek se chalu), Tavily behtar
snippets deta hai par signup maangta hai. Ek interface hone se switch karna ek env var ka
kaam hai, aur test me poora search layer ek line se mock ho jaata hai.

---

## backend/app/tools/duckduckgo_search.py ✅ — **default provider**

`ddgs` package. **Koi API key nahi, koi signup nahi.** Interface `tavily_search` ke bilkul
same hai — `(query, max_results) -> List[str]` — taaki provider badalne pe node me kuch na badle.

Trade-off saaf hai: DDG ke snippets patle hote hain aur wo bina warning ke throttle karta
hai. Lekin zero signup ka matlab hai project pehle din se chalta hai. Key mil jaye to
`SEARCH_PROVIDER=tavily`.

`ddgs` aur purana `duckduckgo_search` dono import handle karte hain — package rename hua tha,
version drift pe import nahi tootna chahiye.

---

## backend/app/tools/tavily_search.py ✅ (optional upgrade)

Tavily client wrapper. `tavily_search(query, max_results) -> List[str]` — sirf snippet text
return karta hai (URL metadata abhi optional). Node ko clean interface deta hai.

## backend/app/tools/vector_search.py ✅

Chroma similarity search wrapper — `retrieve` node aur ingestion script dono use karte hain.
Ek jagah k / score-threshold tuning.

---

## backend/main.py ✅

FastAPI entrypoint. Graph `lifespan` me ek baar compile hota hai (har request pe dobara
banana bewajah kaam hai). `POST /api/query` → `answer`, `source_type`, `relevance_score`,
`transformed_query`, `logs`, `elapsed_ms`. Frontend ka badge + trace viewer isi se banega.

**`run_in_threadpool` kyun:** `graph.invoke` sync hai aur LLM/search calls pe **block** karta
hai. Seedha `async def` me call karne se ek slow request poore event loop ko rok deti — FastAPI
async hone ka poora fayda khatam. Threadpool me bhejne se baaki requests chalti rehti hain.

**`/health` LLM call kyun nahi karta:** healthcheck sasta aur bharosemand hona chahiye. Agar
wo LLM ping karta, to ek rate limit hi container ko unhealthy mark karwa deta aur Docker use
restart karta rehta. Isliye sirf index count + config echo — including `groq_key_set`, jo
setup debug karne me sabse pehle kaam aata hai.

CORS: dev me `allow_origins=["*"]`, Phase 7 me deploy pe frontend origin tak restrict karna
hai — code me TODO pada hai.

**Verified (asli HTTP requests, container me):** `/health` → `{"status":"ok",
"indexed_chunks":22,...}`; khaali question → `422`; bina Groq key ke query → `500` uss saaf
`GROQ_API_KEY set nahi hai` message ke saath.

---

## backend/Dockerfile ✅

1. `python:3.11-slim` base.
2. `requirements.txt` pehle copy + install (layer caching).
3. `app/` + `main.py` copy.
4. FastEmbed model pre-download step (optional) taaki first request slow na ho.
5. `uvicorn main:app --host 0.0.0.0 --port 8000`.

---

## frontend/ (planned — React + Vite + Tailwind)

| File | Kaam |
|---|---|
| `components/ChatBox.jsx` | Query input + message list |
| `components/SourceBadge.jsx` | "Local Vector DB" (green) / "Live Web Fallback" (blue) pill |
| `components/TraceViewer.jsx` | `logs[]` ko node-by-node timeline me render — sabse impressive part, explainability dikhata hai |
| `components/RelevancePill.jsx` | Grading result (`yes`/`no`) transparently |
| `pages/Home.jsx` | Sab compose |
| `vite.config.js` | `/api` proxy to backend in dev |

---

## docker-compose.yml (planned services)

| Service | Image | Kaam |
|---|---|---|
| `backend` | build `./backend` | FastAPI + LangGraph, `vectorstore/` volume mounted |
| `frontend` | build `./frontend` | React build served by Nginx, `/api/` proxy |

Chroma embedded hai (alag service nahi) — persistence sirf ek mounted volume.

---

## .env.example

Real secrets (`.env`) `.gitignore` me. `.env.example` sirf template — batata hai konse vars
chahiye (`GROQ_API_KEY`, `TAVILY_API_KEY`, `VECTOR_DB`) bina real values leak kiye.

---

## Aage jo bhi file banegi, uska explanation yahin niche add hoga.
