# Adaptive CRAG — Complete Interview Prep Documentation
**Adaptive Corrective RAG with Web Search Fallback**

*Author: Nitish | Stack: LangGraph + LangChain + Groq + FastAPI + ChromaDB + DuckDuckGo/Tavily + React*

---

> ## Before reading — what is true right now
>
> **The whole stack is built and running:** ingestion, graph, grading, conditional
> routing, web fallback, groundedness + PII validation, citations, FastAPI, React
> dashboard, docker-compose, and the eval harness. `docker compose up` brings it all up.
> Verified against Groq (`openai/gpt-oss-120b`) and live DuckDuckGo.
>
> **Measured, not claimed** — 20 labelled queries: routing **20/20**, **0 missed
> fallbacks**. Plus 8 ambiguous cases, **8/8 route-stable** across 3 runs, and a second
> corpus (BEIR SciFact) whose labels are not mine. Full analysis in
> [RESULTS.md](../backend/eval/RESULTS.md).
>
> **What that means in an interview:**
> - ✅ You can say *"I implemented the CRAG loop, ran it, and measured it"* — and demo it
>   live, because the UI exists.
> - ✅ You can quote the numbers — **but always with the condition.** 20/20 is on a
>   *categorical* gap (concepts in, live facts out). That means the task is easy, not
>   that the router is perfect. SciFact is the harder number: 78.6%.
> - ✅ **You have two negative results, and they are the strongest thing here** — the
>   latency measurement failed and was withdrawn, and the hybrid + reranker A/B showed
>   **no benefit** (27 of 28 cases retrieved different chunks; not one routing decision
>   moved). Both are written up rather than buried.
> - ❌ **Do not say** "reranking improved retrieval" or "we saved latency" — both were
>   measured and both came back negative.
>   [Section 15](#15-honesty-checklist--what-not-to-claim) is the full list.
> - ❌ **Not deployed.** There is no live link yet. Expect to be asked why.
>
> Sections 15 (what not to claim) and 16 (honest assessment) matter most — read those
> last before an interview.

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
15. **Honesty Checklist — What NOT to Claim** ← read before any interview
16. **How strong this project is — an honest assessment**

---

## 1. The 30-Second Pitch

> "Adaptive CRAG is a self-correcting RAG system. Normal RAG blindly trusts whatever the
> vector database returns — if the retrieved chunks don't actually match the question, the
> LLM still hallucinates an answer out of them. My system adds a grading step: an LLM checks
> whether the retrieved context is actually relevant. If it is, it answers directly. If it's
> not, the agent rewrites the query, runs a live web search to get fresh context, and answers
> from that instead. Every answer then goes through a validation layer that checks it is
> actually grounded in that context, before it is returned."

In one line: *"RAG that catches its own mistake and corrects it — without paying for a web
search on every query, only when one is actually needed."*

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
2. **`retrieve`** — vector search + BM25 over ChromaDB, fused by RRF, then reranked by a
   local cross-encoder down to the top-k chunks.
3. **`grade_documents`** — a cheap LLM call scores: are these chunks relevant/sufficient?
   → `"yes"` or `"no"`.
4. **Outcome A — relevant (`yes`):** straight to `generate`, answer from local context,
   badge = **Local Vector DB**.
5. **Outcome B — not relevant (`no`):** `transform_query` rewrites the question into
   search-optimized keywords → `web_search_fallback` runs a web search and replaces the
   documents with fresh web snippets → `generate` answers from those, badge = **Web Fallback**.
6. **`generate`** — synthesizes an answer grounded strictly in whatever context survived.
7. **`validate_guardrails`** — an independent LLM check that every claim is actually supported
   by the context, plus regex PII redaction, before returning.
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
  ChromaDB + BM25            DuckDuckGo / Tavily
  RRF + cross-encoder       (live web, fallback only)
                    |
                    v
     Output validation  (LLM groundedness check + regex PII redaction)
```

**Why this matters in an interview:** it shows I can separate concerns across an
orchestration layer (LangGraph), a retrieval layer (vector DB), an external-tool layer
(web search), and a validation layer — and wire them with *conditional* control
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

### 6.4 Output Validation Layer
The final answer gets an **independent** groundedness check — a separate temperature-0 LLM
call asking "is every claim here supported by this context?" — plus regex-based PII
redaction, before it's returned.

**Why a second check when the `generate` prompt already says "only from the context":**
a prompt is a request, not a guarantee. The model can quietly fold in training knowledge.
The validation node is a second, independent look at the answer.

**Two decisions worth defending here:**
- **Ungrounded answers are flagged, not blocked.** A warning is prepended; the answer is
  still shown. Seeing a hallucination *get caught* is more convincing than seeing it vanish,
  and "this may be wrong" beats a blank screen for the user. **PII is different** — that gets
  redacted, because flagging a leak is still a leak.
- **The groundedness check fails open.** If the check itself errors (network, rate limit),
  the answer is not blocked — it was built from already-verified context. Failing closed
  would let one flaky call turn the whole system into "I can't tell you anything."

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
| Custom groundedness check, not the Guardrails AI library | The hub-download + version-pinning setup was the biggest time sink in the plan, and the thing that matters is understanding *why* the output needs verifying — two small checks do that with zero extra dependency | No off-the-shelf toxicity/competitor validators; can't claim the library on a CV |
| PII by regex, not by LLM | PII detection should be deterministic and instant | Misses unusual formats a model might catch |
| DuckDuckGo as the default search provider, Tavily behind a config switch | Runs with zero signup, so the project works on day one; the tool layer is abstracted so swapping is one env var | Thinner snippets and undocumented throttling vs a paid API |

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
DuckDuckGo (default) returns thinner snippets than a paid search API and can throttle without
warning; Tavily returns cleaner text but needs a key.
**Mitigation:** `max_results` tuning, the provider is swappable via one env var, and the
validation layer still runs on web-sourced answers — an ungrounded answer from bad web
context gets flagged the same way.

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
it's insufficient." Then a separate validation node runs an independent groundedness check —
is every claim in the answer supported by the context? — and flags the answer if not.

**Q: Why replace the local documents on fallback instead of merging them with web results?**
A: The local docs were just graded "not relevant." Keeping them in the context window
dilutes the good web context and re-introduces the exact hallucination risk I'm trying to
remove. Clean swap is safer.

**Q: How do you handle the grader being wrong?**
A: I accept it's a failure mode and measure it — an eval harness scores grader accuracy on
a labelled set. A false "yes" is the dangerous one; the validation layer is the second net.
A false "no" just costs a web call. Roadmap has a reranking step to give the grader better
input.

**Q: Why did you write your own validation instead of using a guardrails library?**
A: I started with Guardrails AI in the plan. In practice its hub-based validator downloads
and version pinning were going to be the single biggest time sink in the build, and what I
actually needed was two things: is this answer supported by the context, and does it leak
PII. The first is one temperature-0 LLM call, the second is a handful of regexes. Both are
about twenty lines and add no dependency. I'd reach for the library if I needed its
off-the-shelf validators — competitor mentions, jailbreak detection — but for groundedness
the library was overhead, not leverage.

**Q: Why is PII a regex and not another LLM call?**
A: PII detection should be deterministic — the same input must always produce the same
result — and it should be instant. An LLM call there adds latency and variance for no real
gain. The trade-off is that unusual formats slip through, which I'd accept for this scope.

**Q: What happens if the groundedness check itself fails?**
A: It fails open — the answer goes out unflagged, with a note in the trace. It was already
built from verified context, so blocking it on an infrastructure error would be the wrong
call. Failing closed would let a single flaky network call turn the whole system into "I
can't tell you anything."

**Q: Your corpus is seven documents. Isn't that too small to prove anything?**
A: Yes, and that is why there is a second one. The seven-document corpus exists to make
the demo *predictable* — the gap in it is categorical, so the correction path fires on cue
instead of by luck. But it has two limits I couldn't argue my way out of: no ground truth
about which chunk *should* have been retrieved, and I wrote both the documents and the eval
labels. So I added BEIR SciFact behind a `CORPUS` switch. It ships expert relevance
judgments, which means the `local` labels aren't mine, and it makes recall@k possible at
all — did the pipeline actually retrieve the gold document. Each corpus is bad at what the
other is good at, so both stayed.

**Q: Why BEIR specifically, and not a Kaggle dataset or a Wikipedia dump?**
A: Because I needed *labels*, not just volume. A raw dump gives you scale and nothing to
score against — you'd still be writing the eval yourself, which is the bias I was trying to
remove. BEIR is the standard retrieval benchmark suite and every dataset in it ships
`qrels`: which document answers which query, judged by someone else. SciFact in particular
is small enough to embed on a laptop and still large enough that ranking matters.

**Q: You only ingested a subset. Doesn't that invalidate the benchmark?**
A: It would if I'd truncated it, and that's the subtle part. Taking the first N documents
would drop gold documents at random, and then a `local` case would be labelled "the corpus
answers this" when the index genuinely doesn't contain the answer. In the eval that failure
looks like *the router being wrong* — it blames the wrong component, which is the worst
kind of measurement bug. So the subset keeps every gold document first, then fills the rest
with non-gold filler. Filler matters too: without it every indexed document would answer
some query and retrieval would be trivially easy. There's a test asserting both.

**Q: Your eval measures routing. Are the answers actually any good?**
A: That was a real hole, and I filled it late rather than pretending it wasn't there.
Everything else measures the route; groundedness is the only answer-level check and it only
asks whether the answer matches the context it was given — an answer built from the wrong
documents passes it. SciFact is a claim-verification set, so it records whether the gold
abstract supports or contradicts each claim, and twelve of my twenty local cases carry that
label. Baseline: **83.3% correct end to end, 90.9% when the gold document was actually
retrieved**. The two failures are different animals — one where retrieval missed and the
system declined to guess, one where it had the right document and still drew the opposite
conclusion. That is the only real generator error in the run.

Deliberately not LLM-as-judge, and that distinction matters: a judge is asked "is this
good?", which is a model's opinion wearing a number's clothes. Mine is asked only what
position the text takes; right and wrong come from the dataset. The extraction is still the
weak link and I say so in the code — a misread is indistinguishable from a wrong answer.

**Q: Did reranking improve the answers, then?**
A: I don't know yet, and I'd rather say that than guess. Only the baseline arm ran — the
treatment arm hit Groq's daily token cap partway through. The comparison I want is
`answer_verdict_given_gold_pct` between arms, because that subset holds retrieval constant
and isolates what the model actually wrote. Until both arms exist there is nothing to
compare, so nothing in the repo or the dashboard claims there is.

**Q: How would you deploy this?**
A: It isn't deployed, and the interesting part is why the obvious answer doesn't work. The
plan was Render free plus Vercel. I measured it first: the backend peaks at **464 MB** after
one web query on the *smallest* corpus — the cross-encoder and the embedding model are both
resident — against Render free's **512 MB**. Forty-eight megabytes of headroom, so any
concurrency OOMs. Render free also has no persistent disk, which kills the Chroma volume,
and it sleeps after fifteen minutes.

So the target is a HuggingFace Space on the Docker SDK — 16 GB free, no sleep, and the
natural home for an ML demo. One image: Nginx serves the built frontend and proxies `/api/`
to uvicorn, which removes CORS entirely since the origin becomes the same. The vector store
is 12 MB, so it gets baked into the image rather than mounted. `GROQ_API_KEY` goes in HF
Secrets.

**Q: Couldn't you just turn the reranker off and fit inside 512 MB?**
A: Yes, and I measured that too — with hybrid and reranking off it idles at 74 MB and peaks
at **250 MB**, so the cross-encoder plus the BM25 index are about 214 MB of it. It fits
comfortably. I still wouldn't ship it that way: the System Status page would then read
"Hybrid: off, Cross-encoder rerank: off" while the Evaluation page's entire A/B is about
that pipeline. The live demo would not be running the thing I'm showing measurements for,
and the dashboard's one rule is that nothing on screen contradicts the backend. Shrinking
the system to fit a smaller box means hiding the part I most want to talk about.

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

### "Aren't these the same project twice?"

Expect this, and answer it with specifics rather than a denial. **The overlap is real but
it is in the plumbing; the hard parts do not overlap at all.**

**Shared (~40%):** LangGraph `StateGraph` · FastAPI · React · Docker Compose · an eval
harness · the verify-then-correct pattern itself.

**Only in the SQL Agent:**

| | |
|---|---|
| Text-to-SQL, schema and JOIN reasoning | Postgres + SQLAlchemy |
| **Human-in-the-loop approval** — the graph genuinely *pauses* and resumes | **Conversation memory** — Postgres checkpointer, multi-turn |
| **MCP** — client and server, over stdio | Write-safety / destructive-query gating |
| Power BI export | **Deployed** (`render.yaml`) |

**Only in Adaptive CRAG:**

| | |
|---|---|
| **Embeddings, chunking, vector search** — Chroma, FastEmbed, cosine | **Retrieval evaluation** — grading relevance before generating |
| **External tool integration** — live web search behind a provider abstraction | **Groundedness validation** — catching unsupported claims |
| **Eval design for ambiguous cases** — scored for stability, not correctness | Citations |

If someone doubts it, the dependency lists settle it: `sqlalchemy · psycopg2 · mcp` on one
side, `chromadb · fastembed · ddgs` on the other. Almost nothing in common.

### Two answers that land better than "they're different"

**1. The LangGraph construct is different.**
The SQL agent is a **cycle** — the error feeds back into the same node, up to three times.
CRAG is a **branch** — a conditional edge picks one of two paths that merge again. Those
are two different features of the framework, not the same graph twice.

**2. The nature of the error signal is different — and this is the good answer.**

| | SQL Agent | Adaptive CRAG |
|---|---|---|
| How failure announces itself | Postgres raises an error — **objective, external, free** | Nothing happens. Irrelevant chunks still produce a fluent answer — **silent** |
| So the correction trigger is | A fact | An LLM's judgement, which can itself be wrong |
| And therefore | You can watch the loop work | You have to **build a labelled set**, or you cannot know it works at all |

That last row is why CRAG needed an eval harness and the SQL agent did not. *"SQL failure
is loud; retrieval failure is silent"* is a far better answer than "one does SQL, one does
RAG."

### Which one to lead with

| Situation | Lead with |
|---|---|
| RAG / LLM / search role | **Adaptive CRAG** — the retrieval skills exist only here |
| General backend / agent role | **SQL Agent** — more features, and it is deployed |
| Asked "what are you proudest of?" | **CRAG's eval** — the confounded latency run and the ambiguity tier |

**One honest asymmetry to be aware of:** the SQL Agent has a live link, this one does not.
Two projects where one is deployed and one isn't invites "why not?" — deploying this is
the highest-value work left ([ROADMAP](ROADMAP.md)).

---

## 12. Demo Strategy

Judges/interviewers should see the **decision-making live** — grading → routing → fallback
→ validation — not just a chat box.

**Setup:** `docker compose up`, then <http://localhost:3001>. The four demo queries are
buttons in the UI, so you never have to type under pressure — click and talk.

### Scenario 1 — Happy Path (local DB sufficient)
Click *"Why does chunk overlap matter?"*
Flow: `retrieve` → `grade: YES` → `generate` → badge reads **Local Vector DB**.
**Talking point:** "Local knowledge is enough, so no web call — fast and cheap."

### Scenario 2 — Correction Path (the real USP)
Click *"What is the Model Context Protocol?"* — the corpus deliberately never mentions MCP.
Flow: `grade: NO` → `transform_query` (the rewritten query appears in its own panel) →
`web_search_fallback` → `generate` → badge reads **Live Web Fallback**.
**Talking point:** "The system decided *on its own* not to trust local context and corrected
itself — no user input."

Point at the trace while it runs. The two correction nodes are highlighted in blue, so the
moment the system changed course is visible without explaining it.

### Scenario 3 — Guardrail Catch (if time)
Honest framing: on the demo corpus every answer has come back grounded, so there is no
reliable way to *trigger* a catch on demand. Instead, show what the layer does — open
`backend/app/guardrails/validators.py`, explain that an ungrounded answer is flagged rather
than hidden while PII is redacted, and point at the four tests in
`backend/tests/test_validation.py` that cover it.

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
> rewrites queries, and falls back to live web search when local documents are
> insufficient, with a groundedness-validation layer — eliminating hallucinations from
> stale or irrelevant vector-store hits."

---

## 14. Quick Reference — CRAGState Schema

```python
class CRAGState(TypedDict, total=False):
    question: str            # Original user query, never mutated
    transformed_query: str   # Web-optimized search query (fallback path only)
    documents: List[str]     # Working context — REPLACED by web on fallback
    sources: List[str]       # Citations — filenames (local) or URLs (web)
    relevance_score: str     # "yes" or "no" — the conditional edge reads this
    source_type: str         # "vector_db" or "web_search" — drives the UI badge
    generation: str          # Raw synthesized answer
    final_output: str        # Validated answer — what the user receives
    guardrail_passed: bool   # Did validation pass clean
    logs: Annotated[List[str], operator.add]   # Node trace — the only reducer
```

**If asked "why does only `logs` have a reducer?"** — that is the question worth being
ready for, and the answer is the whole project in one sentence:

> "`logs` is additive so every node appends one line and the trace builds itself.
> `documents` is deliberately *not* — an additive reducer there would keep the local
> chunks I just graded irrelevant sitting in the context next to the web snippets that
> replaced them, which re-introduces exactly the hallucination the grading step exists to
> prevent. Same for `sources`, or the UI cites local files under a web-sourced answer.
> There is a test asserting it, because it would break silently."

---

## 15. Honesty Checklist — What NOT to Claim

Overclaiming is the biggest risk. If the interviewer opens the repo and one claim is
false, the whole project's credibility goes — **and it takes the Self-Healing SQL Agent
down with it**, because both are yours. Keep these straight:

| ❌ Don't say | ✅ Say |
|---|---|
| "It validates output with Guardrails AI" | "I dropped Guardrails AI. The hub download and version pinning were going to be the biggest time sink, and what I needed was groundedness plus PII — one temperature-0 call and four regexes, no dependency" |
| **"Routing accuracy is 100%"** — without the condition | Always name the condition. "20/20 on a set where the corpus gap is *categorical* — concepts in, live facts out. That means the labelled task is easy, not that the router is robust. That's why I added ambiguous cases" |
| **"Hybrid search and reranking improved retrieval"** | Only if you name the corpus and the size. "On the 22-chunk corpus the A/B was flat — 27 of 28 questions retrieved different chunks and not one routing decision changed. On SciFact it moved: recall 65→70%, routing 75→78.6%. But that is **one document out of twenty**, which is inside noise. What it establishes is the mechanism — better retrieval, gold document found, correct route — not that reranking reliably helps. That needs the full 5k corpus" |
| **"Routing accuracy is 75% on SciFact"** — stopping there | True but it undersells you. Add the finding: "all seven failures were retrieval misses the grader caught correctly — it made zero independent errors. The bottleneck is retrieval, not grading" |
| **"Adaptive routing saves latency"** | The latency measurement **failed** — Groq's throttling swamps the route difference, and one run showed the local route slower than web. "The cost argument rests on LLM calls per query, 3.0 vs 4.0, which comes from graph structure and is identical on every run" |
| "It has citations with page numbers" | Local answers cite the source **filename**; web answers cite the URL. No page or chunk offsets |
| "It's production ready" | "Portfolio project. It needs CORS restricted, a deploy, prompt-injection handling on the web path, and an incremental re-index pipeline" |
| "The guardrails layer stops prompt injection" | "It's a partial net — an injected instruction usually produces an answer the context doesn't support, so groundedness catches some of it. But it was not designed for that, and the web path is exactly where the risk lives" |
| "The eval proves the grader works" | "It proves the grader handles a categorical gap. One person wrote both the corpus and the labels, which is its own bias — the honest fix is someone else writing cases" |
| "It handles a large knowledge base" | "Seven documents, 22 chunks. That's enough to make the corrective loop demonstrable and measurable. It says nothing about retrieval at scale" |

**Why this matters:** "I didn't build that, and I know why it matters" lands better than
a false "I built everything". Interviewers hunt for gaps — naming them yourself keeps
you in control of the conversation.

---

## 16. How strong this project is — an honest assessment

This section is for you, not the interviewer. It should tell you **what position you are
speaking from**.

### Its strength is not the architecture

LangGraph + conditional routing + web fallback + guardrails is a **published reference
pattern** (Yan et al. 2024, and LangGraph's own CRAG cookbook). Do not present it as
invention, and do not play on the feature-list field — a feature list is the easiest
thing in this repo to reproduce.

**The real strength is three things:**

**1. You published a measurement that failed.**
The first latency comparison looked clean and convincing — local 13.7s vs web 18.5s —
and it was **confounded**. Cases ran in file order, so throttling ramped into the web
bucket and the number measured position, not routing. You found it, interleaved the
cases, and when latency *still* wouldn't separate you dropped it as a metric and moved
the cost argument onto call counts. **That story is worth more than the 20/20.**

**1a. And then you found what the number was hiding.**
On SciFact the router scores 75%. But every case where the gold document *was*
retrieved routed correctly (13/13), and every case where it was *missed* fell back to
the web (7/7). **The grader made zero independent errors** — all seven "routing
failures" were retrieval misses it detected correctly. So 75% understates the grader:
conditional on what it received, it was right 20/20, and the bottleneck is retrieval,
not grading. That is the kind of thing you only see if you instrument the layer *below*
the metric you were reporting.

**1b. And then you published a second one.**
Hybrid search and reranking were added *last*, specifically so the ambiguity tier could
measure them — and the A/B came back flat. Routing 100% → 100%, stability 8/8 → 8/8, and
**27 of 28 questions retrieved different chunks while not one routing decision changed.**
Most people would ship that as "added hybrid retrieval and reranking" and stop. You have
the comparison, and the explanation: on a 22-chunk topically-clustered corpus the verdict
follows topic rather than ranking, and `grade_documents` concatenates its chunks so it
never sees the ordering a reranker optimises.

**2. You designed the eval so it could still fail.**
Routing accuracy was pinned at 100% and could not move, which meant no future retrieval
work could ever be justified. Adding ambiguous cases scored for *stability* rather than
correctness — because their labels are genuinely arguable — is eval design, not eval
usage. Very few candidates have thought about what makes a metric defendable.

**3. Every decision is written down with its cost.**
"Replace local docs, don't merge — you lose a partially useful chunk, but keeping
rejected context reintroduces the exact failure the grading step exists to remove."
"Flag ungrounded answers, don't block; redact PII, because flagging a leak is still a
leak." "Fail open, because failing closed lets one flaky call turn the system into
'I can't tell you anything'." That is trade-off language.

### Weaknesses — know these before you're asked

| Weakness | How big |
|---|---|
| **Seven documents, 22 chunks** | **The biggest technical limit.** It is why the reranker A/B came back flat — at this scale retrieval improvements cannot move a topic-level decision |
| **Not deployed** | **The biggest.** No link means a portfolio project loses half its value |
| The 100% is on an easy gap | You know this and say it first — which is what defuses it |
| No context filter, no PDF parsing | Hybrid + reranker exist but showed no measurable routing benefit — the gap now is corpus scale, not components |
| One author wrote corpus, labels and system | Structural bias — **partly fixed.** The SciFact corpus takes its `local` labels from BEIR's own qrels, so the hard half of that eval is no longer self-written. The `web` half still is |
| Groundedness sits at 85–95%, not investigated | You report it; you have not dug into which answers fail and why |
| No prompt-injection handling | And the web path is where it matters |
| No incremental re-index | Documents are ingested once; updates mean a full rebuild |

**All of these are already in the docs — that is what protects you.** An interviewer
stops hunting once a candidate names their own limits.

### How this differs from the Self-Healing SQL Agent

You will be asked. The answer is **the signal each one corrects on**:

| | SQL Agent | Adaptive CRAG |
|---|---|---|
| Error signal | The database's own error message — **objective, external** | An LLM's judgement of relevance — **subjective, and itself fallible** |
| Correction | Rewrite the SQL, retry (a **cycle**) | Rewrite the query, change source (a **branch**) |
| How you know it worked | The query executes | You had to *build a labelled set* — there is no error to observe |

**That last row is the interesting one.** SQL failure is self-evident; retrieval failure
is silent. That is precisely why CRAG needed an eval harness and the SQL agent's loop
could be watched directly — and it is a much better answer than "one does SQL, one does
RAG."

### Which level this fits

| Level | Verdict |
|---|---|
| **Fresher / 0–2 years** | **Well above** the bar |
| **2–4 years (mid)** | **Competitive** — the eval design is the part that carries it |
| **Senior (5+)** | Not on its own — that needs scale and production traffic. The *thinking* reads senior; the gap is scale |

### Priorities now — and new features are not among them

1. **Deploy it** — highest value left, more than any feature
2. **Learn the eval story cold** — the confounded latency run, in 60 seconds, with numbers
3. **Be able to trace the code yourself** — see [BUILD_PLAN](BUILD_PLAN.md); this is still
   the single biggest risk, because the code will be read as yours
4. **Keep the two demo queries warm** — one local, one web fallback

> **Do not add more features.** What is left is presentation and one deploy, not code.
