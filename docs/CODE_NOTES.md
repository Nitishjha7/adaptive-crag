# Code Notes — Kya Kis Liye Hai

Ye file har file / dependency ka **kaam aur reason** track karti hai, taaki baad me (ya
interview me) yaad rahe ki har cheez kyun li gayi.

**Legend:** ✅ = likha ja chuka · ⬜ = abhi khaali (planned intent).
Phase 1, 2, 3 ✅ ho chuke; Phase 4 se aage ⬜.

---

## backend/requirements.txt ✅

| Package | Kya kaam karta hai | Kyun liya |
|---|---|---|
| `langgraph` | Stateful agent graph — nodes + conditional edges | CRAG ka core. Simple chain se conditional branching (relevant → generate, warna → fallback) express nahi hota; graph chahiye |
| `langchain` / `langchain-core` | LLM abstractions, prompt templates, output parsers | Grader / rewrite / generate sab prompt chains hain. Provider swap karna easy |
| `langchain-groq` | Groq LLM binding | Free tier + bahut fast inference — grading jaisa chhota call latency-sensitive hai |
| `chromadb` | Embedded vector database | Local knowledge base. Zero infra (embedded), Docker volume pe persist ho jaata hai |
| `fastembed` | Lightweight local embedding models (ONNX) | API key nahi chahiye, offline chalta hai, fast. HuggingFace se halka |
| `tavily-python` | Tavily Search API client | Web fallback tool — LLM-optimized snippets deta hai (raw HTML nahi), grounding ke liye clean |
| `guardrails-ai` | Output validation framework | Final answer pe hallucination / PII / toxicity checks. Ungrounded generation catch karta hai |
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
Phase 5 tak API hai hi nahi, aur uske baad bhi debugging ka sabse chhota loop yahi hai.

---

## dev.ps1 ✅ (repo root)

Is machine pe local Python installed nahi hai — sab kuch Docker me chalta hai. Ye helper
lamba `docker run` incantation wrap karta hai: `build` / `ingest [-Reset]` / `ask "..."` / `shell`.

Code **bind-mount** hota hai (`app/`, `data/`, `ingest.py`), isliye edit ke baad rebuild nahi
karna padta — image sirf dependencies deti hai. `.env` `--env-file` se inject hoti hai, image
me bake nahi hoti.

Phase 7 me proper `docker-compose.yml` isko replace kar dega.

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

## backend/app/graph/build_graph.py ✅ (Phase 3 shape)

Graph wiring — nodes register, edges define, `compile()`.

### Abhi ka shape (Phase 3)

- `START → retrieve → grade_documents`.
- `grade_documents` pe conditional edge: `relevance_score == "yes"` → `generate`, warna
  → `transform_query`.
- `transform_query → web_search_fallback → generate`.
- `generate → END`. *(Phase 4 me beech me `validate_guardrails` aayega.)*

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

## backend/app/nodes/validate_guardrails.py ⬜ (Phase 4)

`validate_guardrails` — final safety net.

- `guardrails/validators.py` ka `validate_answer(answer, context, question)` call.
- Checks: groundedness (answer context se supported hai?), PII leak, toxicity.
- Pass → `final_output = generation`. Fail → sanitized / flagged output (v1 me: flag + note).
- Log: `"validate_guardrails -> pass=True/False"`.

---

## backend/app/guardrails/validators.py ⬜ (Phase 4)

Guardrails AI wiring. `Guard` object with validators (`ProvenanceLLM` / `DetectPII` /
`ToxicLanguage` ya custom groundedness). Ek `ValidationResult` return karta hai
(`validated_output`, `passed`).

**Fallback plan:** agar Guardrails AI hub setup heavy pade, ek simple LLM call
("Is this answer fully supported by the context? yes/no") se replace — same interview
talking point, kam dependency.

---

## backend/app/tools/tavily_search.py ✅

Tavily client wrapper. `tavily_search(query, max_results) -> List[str]` — sirf snippet text
return karta hai (URL metadata abhi optional). Node ko clean interface deta hai.

## backend/app/tools/vector_search.py ✅

Chroma similarity search wrapper — `retrieve` node aur ingestion script dono use karte hain.
Ek jagah k / score-threshold tuning.

---

## backend/main.py ⬜ (Phase 5)

FastAPI entrypoint. `build_crag_graph()` ek baar compile (module load pe), `POST /api/query`
har request pe `graph.invoke(initial_state)`. Response me `answer`, `source_type`,
`relevance_score`, `logs` — frontend badge + trace isi se render karta hai. `/health` Docker
healthcheck.

CORS: dev me `allow_origins=["*"]`, production me frontend domain tak restrict. Note kar liya.

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
