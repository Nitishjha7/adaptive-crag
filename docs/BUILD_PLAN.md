# Build Plan — Kaise Chalna Hai

Ye file batati hai ki Adaptive CRAG ko step-by-step kaise build karenge, kaun kya karega,
aur kitna time lagega. Har session ke baad isko update karte rahenge (✅ mark karte jaana).

---

## Working Style

- **Claude (main):** phase-wise chalta hua code likhega — vector store, LangGraph nodes,
  grading, fallback, guardrails, FastAPI, frontend. Har phase ke baad `docker compose up`
  pe run hona chahiye (ya kam se kam `python -m app` se graph invoke ho jaye).
- **Nitish (tu):** har phase ke baad code khud padhega, trace karega, "ye kyun" poochega,
  aur khud ek baar chala ke dono paths (local-hit aur web-fallback) test karega. Ye part
  skip nahi karna — interview me yahi kaam aata hai.
- Ek time pe ek hi phase. Phase pura + run verify hone ke baad hi agla.

---

## Build Schedule (Claude ka output)

| Session | Phase | Deliverable | Status |
|---|---|---|---|
| 1 | Phase 1 + 2 | Chroma ingestion script + persistence, `config.py` (LLM + embedding factory), `CRAGState` schema, LangGraph skeleton (`retrieve` + `generate` + wiring), ek dummy query end-to-end chale | ✅ ingestion (7 docs → 22 chunks) + graph wiring verified |
| 2 | Phase 3 | `grade_documents` binary grader + conditional edge, `transform_query` rewrite, `tavily_search` tool + `web_search_fallback` node, dono paths verify | ✅ dono routes asli Groq + live DuckDuckGo pe verified |
| 3 | Phase 4 + 5 | Custom `validators.py` (LLM groundedness + regex PII — **`guardrails-ai` nahi**) + `validate_guardrails` node, FastAPI `POST /api/query` with step logs + `source_type` | ✅ guardrails ke 4 case + asli HTTP requests verified; `docker-compose.yml` Phase 7 me |
| 4 | Phase 6 + 7 | React + Vite + Tailwind demo UI (ChatBox, SourceBadge, TraceViewer), `/api/` proxy, end-to-end wiring, local run verify, deployment | ⬜ |

**Claude ka effort:** ~4 working sessions. Back-to-back karein toh 1–2 din.

---

## Nitish ka Part (interview-ready banne ke liye)

Har phase ke baad:
1. [CODE_NOTES.md](CODE_NOTES.md) padh — us phase ki files ka "kya / kyun"
2. Code line-by-line trace kar, jo samajh na aaye Claude se pooch
3. Graph khud invoke karke dono routes chala:
   - ek query jiska answer local docs me hai → `grade: yes` → direct generate
   - ek query jiska answer local docs me nahi hai → `grade: no` → transform → web → generate
4. [INTERVIEW_NOTES.md](INTERVIEW_NOTES.md) ka relevant Q&A bolke practice kar

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

1. Phase 1 — vector store ingestion + Chroma persistence + config
2. Phase 2 — LangGraph skeleton: `CRAGState`, `retrieve`, `generate`, edges
3. Phase 3 — `grade_documents` + conditional edge + `transform_query` + Tavily fallback
4. Phase 4 — Guardrails AI output validation layer
5. Phase 5 — FastAPI `/api/query` endpoint with step logs
6. Phase 6 — React + Vite + Tailwind demo UI (source badges, trace viewer)
7. Phase 7 — Docker Compose + deployment (Render + Vercel)
8. Eval script + INTERVIEW_NOTES me real numbers bharna

Detail har phase ka [ROADMAP.md](ROADMAP.md) me hai.

---

## Known Time-Sinks (jahan atkega)

- **Guardrails AI setup** — validator install / hub download, version pinning. Agar zyada
  atke toh ek simple custom groundedness check (LLM "is this answer supported by context?")
  se replace kar dena — same interview point.
- **Grader consistency** — LLM kabhi "yes"/"no" ke bajaye explanation de deta hai. Prompt
  tight rakhna + output parse defensively (`"yes" in verdict`).
- **Fallback determinism** — demo me web search results badalte rehte hain. Controlled
  dataset + fixed demo queries use karna.
- **Embedding model download** — pehli baar FastEmbed model pull karta hai (~100MB), Docker
  layer me cache karna.

---

## Next Step

Claude Phase 1 se code likhna start karega. Nitish ready ho toh bolo "Phase 1 shuru karo".
