# Build Plan — Kaise Chalna Hai

Ye file batati hai ki Adaptive CRAG ko step-by-step kaise build karenge, kaun kya karega,
aur kitna time lagega. Har session ke baad isko update karte rahenge (✅ mark karte jaana).

---

## Working Style

- **Claude (main):** ✅ **ho gaya** — phase-wise code likha (vector store, LangGraph nodes,
  grading, fallback, validation, FastAPI, frontend), har phase ke baad run karke verify kiya.
- **Nitish (tu):** ⬜ **abhi baaki** — code khud padhna, trace karna, "ye kyun" poochna, aur
  khud dono paths chala ke dekhna. Ye part skip nahi karna — interview me yahi kaam aata hai.
  Detail neeche "Nitish ka Part" me hai.

---

## Build Schedule (Claude ka output)

| Session | Phase | Deliverable | Status |
|---|---|---|---|
| 1 | Phase 1 + 2 | Chroma ingestion script + persistence, `config.py` (LLM + embedding factory), `CRAGState` schema, LangGraph skeleton (`retrieve` + `generate` + wiring), ek dummy query end-to-end chale | ✅ ingestion (7 docs → 22 chunks) + graph wiring verified |
| 2 | Phase 3 | `grade_documents` binary grader + conditional edge, `transform_query` rewrite, `tavily_search` tool + `web_search_fallback` node, dono paths verify | ✅ dono routes asli Groq + live DuckDuckGo pe verified |
| 3 | Phase 4 + 5 | Custom `validators.py` (LLM groundedness + regex PII — **`guardrails-ai` nahi**) + `validate_guardrails` node, FastAPI `POST /api/query` with step logs + `source_type` | ✅ guardrails ke 4 case + asli HTTP requests verified |
| 4 | Phase 6 + 7 | React + Vite + Tailwind demo UI (ChatBox, SourceBadge, TraceViewer, RelevancePill), `/api/` proxy, `docker-compose.yml`, end-to-end wiring | ✅ `docker compose up` se poora stack chalta hai; dono routes UI se verified. Deployment abhi baaki |

**Claude ka effort:** ~4 working sessions. Back-to-back karein toh 1–2 din.

---

## Nitish ka Part (interview-ready banne ke liye) — ⬜ **ye abhi bacha hua hai**

Code ban chuka hai. **Ye wala part nahi hua** — aur interview me exactly yahi kaam aata hai.
Code jo maine likha wo tere naam se jaayega; agar tu trace nahi kar sakta to wahi sabse
bada risk hai.

1. [CODE_NOTES.md](CODE_NOTES.md) padh — har file ka "kya / kyun"
2. Code line-by-line trace kar, jo samajh na aaye pooch. Yahan se shuru kar (yahi core hai):
   - `backend/app/nodes/grade_documents.py` — grader + `parse_verdict`
   - `backend/app/graph/build_graph.py` — `decide_to_generate` conditional edge
   - `backend/app/nodes/web_search_fallback.py` — docs replace kyun, merge kyun nahi
   - `backend/app/schemas/crag_state.py` — `logs` pe reducer, `documents` pe kyun nahi
3. Dono routes khud chala:
   ```powershell
   .\dev.ps1 ask "why does chunk overlap matter?"              # grade: yes -> local
   .\dev.ps1 ask "what is the model context protocol?"          # grade: no  -> web
   ```
   Trace me har node dekh. Phir UI pe wahi kar — <http://localhost:3001>
4. **Ek test jaan-boojh ke todh ke dekh** — samajhne ka sabse tez tareeka. Jaise
   `web_search_fallback.py` me `"documents": snippets` ko append karne wala bana de aur
   `.\dev.ps1 test` chala; dekh kaunsa test fail hota hai aur kyun. Phir wapas theek kar.
5. [INTERVIEW_NOTES.md](INTERVIEW_NOTES.md) ka Q&A bolke practice kar — khaas kar trade-offs
   aur "why not Guardrails AI" wale.

**Nitish ka effort:** ~3–4 din (daily 2–3 ghante).

---

## Total Timeline

| Scenario | Time |
|---|---|
| Sirf chalta hua code (Claude) | ~4 sessions / 1–2 din |
| Code + tu confidently explain kar sake | **~4–5 din** (daily 2–3 ghante) |
| Interview-ready MVP (dono paths solid, guardrails on, minimal UI, trace visible) | ~7–8 din |

---

## Order of Execution

1. ✅ Phase 1 — vector store ingestion + Chroma persistence + config
2. ✅ Phase 2 — LangGraph skeleton: `CRAGState`, `retrieve`, `generate`, edges
3. ✅ Phase 3 — `grade_documents` + conditional edge + `transform_query` + web fallback
4. ✅ Phase 4 — output validation (groundedness + PII)
5. ✅ Phase 5 — FastAPI `/api/query` endpoint with step logs
6. ✅ Phase 6 — React + Vite + Tailwind demo UI (source badges, trace viewer)
7. ✅ Phase 7 — Docker Compose · ❌ deployment (Render + Vercel) abhi baaki
8. ❌ Eval script + INTERVIEW_NOTES me real numbers bharna

Detail har phase ka [ROADMAP.md](ROADMAP.md) me hai.

---

## Time-Sinks — plan vs reality

| Jo socha tha | Jo actually hua |
|---|---|
| **Guardrails AI setup** sabse bada atkaav hoga | Library **li hi nahi**. Fallback plan (custom LLM groundedness check + regex PII) seedha liya — 20 min ka kaam, zero dependency. Sahi call tha |
| **Grader consistency** — LLM explanation de dega | Ab tak nahi hua; `openai/gpt-oss-120b` saaf `yes`/`no` deta hai. Phir bhi `parse_verdict` defensive hai aur uske 11 test cases hain |
| **Fallback determinism** — web results badalte hain | Controlled corpus + deliberate gap se handle ho gaya. Paanchon fixed queries sahi route leti hain |
| **Embedding model download** (~100MB) | Dockerfile me build-time pe cache kiya — pehli request slow nahi hoti |

### Jo socha hi nahi tha (asli atkaav yahan aaye)

- **Machine pe Python hi nahi tha** — sirf WindowsApps stub. Sab kuch Docker me chalana pada;
  `dev.ps1` isi wajah se bana.
- **Groq pe `llama-3.3-70b-versatile` available nahi tha** — 404 `model_not_found`.
  `/v1/models` list karke `openai/gpt-oss-120b` pe switch kiya. **Ye mocks ne kabhi nahi
  pakda hota** — isiliye asli run zaroori tha.
- **`ingest.py --reset` Docker me crash** — `vectorstore/` ek mount point hai, `rmtree` pe
  `Device or resource busy`. Contents clear karne se fix.
- **Compose me pehli query pe 502** — `depends_on: service_started` se nginx uvicorn se
  pehle up ho jaata tha. `service_healthy` se fix.
- 🔴 **Asli Groq key `.env.example` me chali gayi** — wo file commit hoti hai (`.env` gitignored
  hai, `.env.example` nahi). Key commit `7dac9b5` me hai, wo push ho chuki hai, aur repo
  **public** hai. **Ye abhi tak revoke nahi hui — sabse pehla kaam yahi hai:**
  [console.groq.com/keys](https://console.groq.com/keys) pe jaake delete karo, nayi banao,
  nayi sirf `.env` me daalo.

---

## Next Step

Backend + frontend + compose sab chal rahe hain. Ab do cheezein bachi hain:

1. **Eval script** (`eval/scenarios.json` + runner) — abhi koi accuracy measure nahi hui,
   isliye interview me koi number quote nahi kar sakte. Ye sabse zyada value deta hai.
2. **Deployment** — Render (backend) + Vercel (frontend).
