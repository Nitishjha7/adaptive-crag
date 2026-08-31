# Adaptive CRAG — Complete Interview Prep Documentation
**Adaptive Corrective RAG with Web Search Fallback**

*Author: Nitish | Stack: LangGraph + LangChain + FastAPI + ChromaDB + Tavily + Guardrails AI + React*

---

> ## ⚠️ Padhne se pehle — ye abhi bana nahi hai
>
> `backend/` ki saari files khaali hain. Ye doc **intended** system ka hai, chal
> rahe code ka nahi. Interview me ise "banaya hai" bol dena aur interviewer ka
> GitHub khol lena — sabse bada credibility risk hai, aur wo tumhare
> **Self-Healing SQL Agent** pe bhi shak daal dega, jo actually bana hua hai.
>
> **Jab tak implementation nahi hoti, aise bolo:**
> *"CRAG design kar chuka hoon — retrieval grading with conditional web fallback.
> Architecture aur trade-offs pe detail me baat kar sakta hoon; implementation abhi
> chal rahi hai."*
>
> Ye honest bhi hai aur architectural thinking bhi dikhata hai. Build order
> [ROADMAP.md](ROADMAP.md) me hai. Implementation ke baad ye banner hata dena.

---

## Table of Contents
1. The 30-Second Pitch
2. The Problem (Why This Project Exists)
3. Is This Real or Just a Portfolio Toy?
4. What the System Actually Does (Full Flow)
5. Architecture Overview
6. Core Features & USPs (Deep Dive)
7. Design Trade-offs
8. Limitations & Mitigations
9. How to Present This in an Interview (Script + Structure)
10. Anticipated Interview Questions (Technical + Product)
11. Positioning Alongside Other Projects
12. Demo Strategy
13. One-Liner for Resume/LinkedIn
14. Quick Reference — CRAGState Schema

---

## 1. The 30-Second Pitch

> "Adaptive CRAG is a self-correcting RAG system. Normal RAG blindly trusts whatever the
> vector database returns — if the retrieved chunks don't actually match the question, the
> LLM still hallucinates an answer out of them. My system adds a grading step: an LLM checks
> whether the retrieved context is actually relevant. If it is, it answers directly. If it's
> not, the agent rewrites the query, runs a live web search to get fresh context, and answers
> from that instead. Every answer goes through a guardrails layer for hallucination and PII
> checks before it's returned."

Ek line me: *"RAG jo apni khud ki galti pakadta hai aur khud fix karta hai — bina hamesha
web search pe depend kiye, sirf jab zaroorat ho tab."*

Say the pitch **first**, before any tech talk. It frames everything as a solution to a real
failure mode, not a feature list.

---

## 2. The Problem (Why This Project Exists)

Traditional / naive RAG works on one assumption: **whatever came back from the vector DB is
relevant.** That breaks in two ways:

1. **Hallucination on retrieval mismatch** — if the retrieved chunks don't match the query,
   the LLM still stitches together a plausible-sounding but wrong answer from them.
2. **Staleness** — if the local knowledge base is outdated (new event, changed fact), the
   system confidently returns old info because it has no way to know its own data is
   insufficient.

CRAG solves both with a **verification-first approach**: grade the context before trusting it.

---

## 3. Is This Real or Just a Portfolio Toy?

**Be honest if asked — it builds credibility.**

The pattern is real and published:
- **Corrective RAG (CRAG)** — Yan et al., 2024 — the paper this is based on.
- **Self-RAG** — same family: models that critique their own retrieval.
- **LangGraph's own CRAG cookbook** — this is a recognized reference architecture, not
  something I invented.

Production RAG systems at scale (Perplexity-style answer engines, enterprise support bots)
all do some version of "retrieve → judge → maybe fall back." What this project demonstrates
is that I can build the **agentic control loop** — conditional routing, state threading,
autonomous correction — from scratch with LangGraph, not just call a `RetrievalQA` chain.

**Positioning:** I'm not claiming a novel algorithm. I'm showing I understand *why* naive RAG
fails and can architect the fix.

---

## 4. What the System Actually Does (Full Flow)

1. User asks a question.
2. **`retrieve`** — vector similarity search against ChromaDB returns the top-k local chunks.
3. **`grade_documents`** — a cheap LLM call scores: are these chunks relevant/sufficient?
   → `"yes"` or `"no"`.
4. **Outcome A — relevant (`yes`):** straight to `generate`, answer from local context,
   badge = **Local Vector DB**.
5. **Outcome B — not relevant (`no`):** `transform_query` rewrites the question into
   search-optimized keywords → `web_search_fallback` runs a Tavily search and replaces the
   documents with fresh web snippets → `generate` answers from those, badge = **Web Fallback**.
6. **`generate`** — synthesizes an answer grounded strictly in whatever context survived.
7. **`validate_guardrails`** — checks the answer for hallucination (is it actually supported
   by the context?), PII leakage, and toxicity before returning.
8. Response carries the answer, the `source_type`, the relevance score, and a full
   node-by-node execution log.

---

## 5. Architecture Overview

```
React + Vite + Tailwind Frontend
  |-- Chat UI
  |-- Source badge (Local Vector DB / Live Web Fallback)
  \-- Execution-trace viewer (which node ran, in what order)
                    |
                    v
FastAPI Backend  (POST /api/query)
                    |
                    v
LangGraph StateGraph  (CRAGState threaded through every node)
   retrieve -> grade_documents -> [conditional evaluator]
        |-- yes --> generate ---------------------------+
        \-- no  --> transform_query -> web_search_fallback -> generate
                                                             |
                                                             v
                                                   validate_guardrails -> final_output
                    |
       +------------+------------+
       v                         v
  ChromaDB / FAISS          Tavily / DuckDuckGo
  (local embeddings)        (live web, fallback only)
                    |
                    v
              Guardrails AI  (hallucination / PII / toxicity)
```

**Why this matters in an interview:** it shows I can separate concerns across an
orchestration layer (LangGraph), a retrieval layer (vector DB), an external-tool layer
(web search), and a validation layer (Guardrails) — and wire them with *conditional* control
flow, not a linear pipeline.

---

## 6. Core Features & USPs (Deep Dive)

### 6.1 Self-Grading Retrieval
Before generating anything, a dedicated LLM node grades whether the retrieved chunks are
relevant (`"yes"`/`"no"`). It's a small, cheap, temperature-0 call. No blind trust.

**Why it matters:** this single step is the entire difference between naive RAG and CRAG.
It's where hallucination gets caught.

### 6.2 Autonomous Web Fallback
When local context is graded insufficient, the agent *itself* decides to rewrite the query
and go to the web — the user never has to say "search the internet." The fallback is
conditional, so a good local hit never pays the web-search cost or latency.

**Why it matters:** "adaptive" means the execution path is decided at runtime from the
grading output, not fixed.

### 6.3 Query Transformation
User questions are conversational; search engines want keywords. A rewrite node converts
"can you help me understand how X works in the new version" into a tight keyword query
before the web search.

### 6.4 Guardrails Validation Layer
The final answer is scanned for groundedness (is every claim supported by the context?),
PII leakage, and toxic content before it's returned — so the LLM can't quietly inject
its own training knowledge.

### 6.5 Full Execution Trace
Every node appends to a `logs` list threaded through the state. The frontend renders this
as a node-by-node timeline, so you can *see* the decision: retrieve → grade: no →
transform → web search → generate → validate. Explainability, not a black box.

---

## 7. Design Trade-offs

| Decision | Why | Cost |
|---|---|---|
| LangGraph, not a LangChain chain | Need conditional branching + a corrective loop; a chain is linear | Slightly more boilerplate to wire nodes/edges |
| Web search as fallback, not always-on | Local hit is faster and cheaper; most queries are answerable locally | One extra LLM grading call per query |
| Replace local docs on fallback (not merge) | Docs already graded "no" — keeping them dilutes context and re-introduces hallucination risk | Lose any partially-useful local chunk |
| Both branches merge back into one `generate` | DRY; `generate` only reads `state["documents"]`, doesn't care about source | None meaningful |
| Binary grader (`yes`/`no`), not a 0–1 score | Simple, deterministic routing; easy to explain | Coarser — no "partially relevant" handling in v1 |

---

## 8. Limitations & Mitigations

Bring these up **proactively** — it signals maturity.

### Limitation 1 — Grader is itself an LLM
The relevance grader can be wrong (false "yes" → hallucination slips through; false "no" →
unnecessary web call).
**Mitigation:** temperature 0, a tightly constrained prompt, defensive parsing. Longer term,
an evaluation harness measures grader accuracy on a fixed labelled set, and a reranking step
before grading gives it better chunks to judge.

### Limitation 2 — Web fallback quality depends on the search API
Tavily can return thin or off-topic snippets for niche queries.
**Mitigation:** `max_results` tuning, and the guardrails layer still runs on web-sourced
answers — an ungrounded answer from bad web context gets flagged the same way.

### Limitation 3 — No multi-hop reasoning
A compound question ("compare X's v2 pricing to v1") gets one retrieval pass, not decomposed
sub-queries.
**Mitigation:** roadmap Phase 9 — query decomposition. Out of scope for the MVP, called out
honestly.

### Limitation 4 — Latency on the correction path
The `no` path is grade → rewrite → search → generate → validate: four to five LLM/API calls.
**Mitigation:** Groq for fast inference on the small calls; streaming the final `generate`
tokens to the frontend (roadmap) so perceived latency drops.

### Limitation 5 — Local knowledge base is static
Documents are ingested once; there's no re-index pipeline.
**Mitigation:** acceptable for a demo with a controlled dataset; production would add a
scheduled ingestion job.

---

## 9. How to Present This in an Interview (Script + Structure)

**Order:**
1. **Problem first** (15 sec) — naive RAG blindly trusts retrieval → hallucination + staleness.
2. **Solution overview** (30 sec) — the 30-second pitch from Section 1.
3. **Pick 2–3 deep dives** based on the interviewer:
   - agentic/systems interviewer → LangGraph conditional routing + state threading
   - RAG/ML interviewer → the grader, fallback decision, groundedness validation
   - product interviewer → the cost/latency trade-off of conditional fallback
4. **Proactively mention one trade-off** (Section 7).
5. **If time allows, limitations + mitigations** (Section 8) — strong closer.

**Golden rules:**
- Never open with "I used LangGraph" — open with the failure mode it fixes.
- Always connect a technical choice to an outcome (cost, latency, reliability).
- State trade-offs before being asked.

**Tech-to-outcome pattern to memorize:**
> "I made web search a fallback instead of always running it — not to save an API call for
> its own sake, but because the whole value of RAG is that a local hit is fast and cheap.
> If I searched the web on every query, I'd have a slow, expensive answer engine, not a
> corrective RAG system. The grading call is the price I pay to keep the common path fast."

---

## 10. Anticipated Interview Questions (Technical + Product)

### Technical

**Q: Why LangGraph and not a plain LangChain chain?**
A: I need conditional branching and a corrective loop — the path depends on the grader's
output at runtime. A chain is linear. LangGraph gives me a `StateGraph` with conditional
edges, and the state object threads the full execution trace through every node.

**Q: Why not just always do web search?**
A: Cost and latency. Most queries are answerable from the local knowledge base, and a local
vector lookup is milliseconds vs a web round-trip plus more tokens. The fallback fires only
when grading says local context is insufficient — that one extra grading call is cheap
insurance.

**Q: How does the grading step actually work?**
A: A temperature-0 LLM call with a tightly constrained prompt — "answer yes or no, does this
context help answer the question, don't explain." I parse defensively (`"yes" in output`)
because LLMs sometimes add text. It's a binary classifier, deliberately coarse so routing
is deterministic and explainable.

**Q: What stops the LLM from answering from its own training knowledge instead of the context?**
A: Two things. The `generate` prompt says "answer only from the provided context, say so if
it's insufficient." Then the guardrails layer runs a groundedness check — is every claim in
the answer actually supported by the context? — and flags the answer if not.

**Q: Why replace the local documents on fallback instead of merging them with web results?**
A: The local docs were just graded "not relevant." Keeping them in the context window
dilutes the good web context and re-introduces the exact hallucination risk I'm trying to
remove. Clean swap is safer.

**Q: How do you handle the grader being wrong?**
A: I accept it's a failure mode and measure it — an eval harness scores grader accuracy on
a labelled set. A false "yes" is the dangerous one; the guardrails layer is the second net.
A false "no" just costs a web call. Roadmap has a reranking step to give the grader better
input.

**Q: How would you deploy this?**
A: FastAPI backend in a Docker container on Render, Chroma persisted to a mounted volume,
React frontend on Vercel with an `/api` proxy. Groq for the LLM, Tavily for search, both
via env-injected keys.

**Q: How does this scale?**
A: The stateless FastAPI layer scales horizontally. The bottleneck is the vector store —
for real scale I'd move from embedded Chroma to a managed service (Pinecone / Weaviate /
Chroma Cloud) and add a reranker. The LLM calls are already on a fast hosted provider.

### Product / Business

**Q: Where would this actually be used?**
A: Any RAG product where the knowledge base has gaps or goes stale — internal support bots,
documentation assistants, research tools. The corrective loop is what lets you ship a RAG
bot without it confidently lying when it hits a gap.

**Q: How would you measure if it's working?**
A: Three metrics — grading accuracy (vs human labels), fallback precision (did it only go
to the web when local really was insufficient), and groundedness rate of final answers.
I'd run these on a fixed 15–20 query set with known expected routes.

---

## 11. Positioning Alongside Other Projects

Present this as a **pattern**, not an isolated project:

> **"Agentic Self-Correcting Systems"** — Self-Healing SQL Agent (fixes SQL *execution
> errors* by reading the DB error and retrying) and Adaptive CRAG (fixes *retrieval
> relevance* by grading context and falling back to web). Same architecture — LLM +
> self-verification + autonomous correction — applied to two different failure domains.

This shows a recruiter you understand an architectural pattern, not just one trick.

**If asked "do these overlap?":** No — they share the *pattern* but the correction targets
are different (execution errors vs retrieval quality). Together they make one coherent
skill-area story.

---

## 12. Demo Strategy

Judges/interviewers should see the **decision-making live** — grading → routing → fallback
→ validation — not just a chat box.

### Scenario 1 — Happy Path (local DB sufficient)
Pre-ingest a small controlled doc set (5–10 docs). Ask a question answerable from them.
Flow: `retrieve` → `grade: YES` → `generate` → **"Source: Local Vector DB"**.
**Talking point:** "Local knowledge is enough, so no web call — fast and cheap."

### Scenario 2 — Correction Path (the real USP)
Ask a question the local docs deliberately don't cover (leave a gap in the dataset).
Flow: `grade: NO` → `transform_query` (show the rewritten query) → `web_search_fallback`
→ `generate` → **"Source: Web Fallback"**.
**Talking point:** "The system decided *on its own* not to trust local context and corrected
itself — no user input."

### Scenario 3 — Guardrail Catch (if time)
A tricky/ambiguous query with hallucination risk; show the guardrails layer validating
(or flagging) the output.

### What to highlight in the UI
- **Source badge** on every answer (Local DB vs Web Fallback)
- **Execution trace / step logs** — which node ran, in what order (most impressive part)
- **Relevance score** shown transparently (`yes`/`no`)

### Practical tip
Use a small controlled dataset and fixed demo queries so the fallback triggers predictably
— avoid live randomness. Keep screenshots of the trace logs for your portfolio.

---

## 13. One-Liner for Resume/LinkedIn

> "Built Adaptive CRAG — a LangGraph agentic RAG system that self-grades retrieved context,
> rewrites queries, and falls back to live web search (Tavily) when local documents are
> insufficient, with a Guardrails AI validation layer — eliminating hallucinations from
> stale or irrelevant vector-store hits."

---

## 14. Quick Reference — CRAGState Schema

```python
class CRAGState(TypedDict):
    question: str            # Original user query
    transformed_query: str   # Web-optimized search query
    documents: List[str]     # Retrieved chunks (local, or web on fallback)
    relevance_score: str     # "yes" or "no"
    source_type: str         # "vector_db" or "web_search"
    generation: str          # Raw synthesized answer
    final_output: str        # Guardrail-validated final response
    logs: List[str]          # Node trace execution logs
```
