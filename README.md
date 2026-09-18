<div align="center">

# Adaptive Corrective RAG

**A RAG pipeline that grades its own retrieval before answering — and searches the web only when it decides the corpus falls short.**

[![tests](https://github.com/Nitishjha7/adaptive-crag/actions/workflows/ci.yml/badge.svg)](https://github.com/Nitishjha7/adaptive-crag/actions/workflows/ci.yml)
[![missed fallbacks](https://img.shields.io/badge/missed%20fallbacks-0%20on%20both%20corpora-3fb950)](#what-the-measurements-say)
[![SciFact recall@k](https://img.shields.io/badge/SciFact%20recall%40k-70%25-0d9488)](backend/eval/RESULTS.md)
[![LangGraph](https://img.shields.io/badge/LangGraph-StateGraph-4f46e5)](backend/app/graph/build_graph.py)
[![Groq](https://img.shields.io/badge/Groq-gpt--oss--120b-f97316)](backend/app/config.py)
[![license](https://img.shields.io/badge/license-MIT-64748b)](LICENSE)

</div>

Naive RAG trusts whatever the vector DB returns. CRAG adds a verification step: a
grading node decides whether the retrieved chunks actually answer the question,
and only pays for a web call when they don't.

**The point of the project is not the loop — it is measuring whether the loop
works.** Routing accuracy, retrieval recall and answer correctness are all
measured against labelled sets, and the results that came back negative are
published alongside the ones that didn't.

---

<p align="center">
  <img src="docs/images/architecture.svg" alt="Architecture: a question is retrieved with hybrid search and reranking, graded by an LLM, then either answered locally or corrected through query rewriting and web search before generation and guardrails" width="100%">
</p>

<p align="center">
  <sub>Indigo is the one node the <b>model</b> controls — everything downstream is a
  deterministic edge reading its verdict. The correction path costs one extra LLM call,
  and only runs when the grader says the corpus is not enough.</sub>
</p>

---

## What it looks like

Every answer carries its own execution trace. Here the local route, with **web
search shown as skipped** — the fallback is conditional, not the default. The LLM
call count comes from the trace, and names the cost of the path not taken.

![Chat with the execution trace expanded](docs/images/trace.png)

The evaluation page leads with *who labelled the test set*, then two experiments
with their real tables — including the one where reranking changed 27 of 28
retrievals and moved zero routing decisions.

![Evaluation page](docs/images/evaluation.png)

<details>
<summary>Documents and System Status</summary>

![Documents page](docs/images/documents.png)
![System status page](docs/images/system.png)

</details>

---

## What the measurements say

Two corpora. `concepts` is 7 hand-written documents with a deliberate gap.
`scifact` is BEIR SciFact — 500 abstracts whose relevance labels ship with the
dataset, so they are not mine.

| | concepts | SciFact |
|---|---|---|
| Routing accuracy | 20/20 | 22/28 (78.6%) |
| **Missed fallbacks** (the expensive error) | **0** | **0** |
| Retrieval recall@k | no ground truth | 70% |
| Answer correctness † | no ground truth | 83.3% (90.9% given gold retrieved) |
| LLM calls per query | local 3 · web 4 | same |

† Measured on the **baseline** arm (vector-only retrieval); every other SciFact
number is the shipped hybrid + rerank config. The treatment arm of that A/B hit
Groq's daily token cap, so the two are not yet comparable on answer quality —
see [what is not built](#what-is-not-built).

Three findings that matter more than the scores:

- **100% means the labelled task is easy, not that the router is perfect.** The
  concepts gap is categorical by design, and I wrote both the corpus and the
  labels. That is why SciFact exists.
- **The grader made zero independent errors.** On SciFact every case whose gold
  document was retrieved routed correctly (13/13) and every case that missed it
  fell back (7/7). Every "routing failure" was a retrieval miss the grader caught.
  The bottleneck is retrieval, not grading — and the same holds one stage down:
  given the right document, the generator was right 10 times out of 11.
- **Reranking changed nothing measurable, and that is written down.** Hybrid
  search and cross-encoder reranking were A/B'd behind flags. On concepts, 27 of
  28 questions retrieved *different* chunks and not one verdict moved. On SciFact
  exactly one case changed. Latency could not be measured at all — the first
  number looked convincing and turned out to be a throttling artifact, so no
  latency figure is reported anywhere.

Full analysis, including both negative results and what is still unproven:
**[backend/eval/RESULTS.md](backend/eval/RESULTS.md)**.

---

## Run it

Only `GROQ_API_KEY` is required — web search defaults to DuckDuckGo, no key.

```bash
cp .env.example .env       # fill in GROQ_API_KEY
docker compose up --build
```

- Frontend → <http://localhost:3001>
- API docs → <http://localhost:8001/docs>

Switch corpus without editing anything:

```bash
CORPUS=scifact docker compose up -d --build   # BEIR SciFact, 1,717 chunks
docker compose up -d                          # back to concepts
```

The demo questions, the evaluation findings and the corpus notes all follow
`CORPUS` — SciFact numbers under prose written about concepts would have the
dashboard contradicting its own figures.

Backend-only dev loop (`.\dev.ps1 test`, `ingest`, `eval`, `ask`) is in
[docs/SETUP.md](docs/SETUP.md).

---

## How it works

1. **`retrieve`** — vector search + BM25 over ChromaDB, fused by RRF, reranked by
   a local cross-encoder to the top-k chunks.
2. **`grade_documents`** — an LLM binary grader: is this context sufficient,
   `yes` or `no`?
3. **`yes` →** straight to `generate`.
4. **`no` →** `transform_query` rewrites into search keywords →
   `web_search_fallback` replaces the rejected documents → `generate`.
5. **`generate`** — answers strictly from the surviving context.
6. **`validate_guardrails`** — independent groundedness check plus PII redaction.

| Layer | Technology |
|---|---|
| Orchestration | LangGraph (StateGraph), conditional edges |
| LLM / embeddings | Groq · FastEmbed (`bge-small-en-v1.5`, local ONNX) |
| Retrieval | Chroma + BM25, RRF fusion, `ms-marco-MiniLM` cross-encoder |
| Web fallback | DuckDuckGo (default) / Tavily (optional) |
| Validation | LLM groundedness check + regex PII redaction |
| API / UI | FastAPI · React + Vite + Tailwind · Docker Compose |
| LLM gateway | Groq → Groq fallback chain (`with_fallbacks`) — same-provider, since this project has one key |
| Observability | Per-query token/cost accounting, Prometheus `/metrics`, JSON stdout logs |

---

## Live, streaming, and observable

Beyond the batch `POST /api/query`, the same graph is exposed three more ways:

- **`POST /api/query/stream`** — Server-Sent Events. One `progress` event per
  finished graph node, phrased around the routing decision itself
  (`grade_documents: relevance=no (not relevant, falling back to web)`), then a
  final `done` event with the exact payload `/api/query` returns. Verified live
  against real Groq and real DuckDuckGo, one local-route and one web-fallback
  query — see [backend/eval/RESULTS.md](backend/eval/RESULTS.md#call-counts-upgraded-to-real-tokens-and-dollars).
- **`get_llm()` fallback chain** — this project already lived through a real
  incident (Groq retired `llama-3.3-70b-versatile` mid-project, see
  [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md)). Setting `LLM_FALLBACK_MODELS`
  wires a `with_fallbacks()` chain so a dead or rate-limited primary fails over
  to a second Groq model, with temperature preserved through the whole chain
  (grading needs temp=0 determinism regardless of which model actually
  answers). Empty by default — no fallback simulated unless configured.
- **`/metrics`** (Prometheus) + JSON stdout logs — routing counts, groundedness
  pass/fail, LLM calls/tokens/cost by model, and whether a fallback fired.
  Every metric mirrors something `eval/RESULTS.md` already measures offline;
  nothing generic was added.
- **Per-query token and cost accounting** — the precise replacement for the
  "3 calls vs 4 calls" proxy the eval fell back on after latency proved
  unmeasurable. Both `/api/query` and `/api/query/stream` return `token_usage`
  with real input/output tokens and USD cost per model.
- **Cross-query memory (`app/memory/`)** — episodic and semantic, both real
  vector similarity through the same FastEmbed/Chroma pair `retrieve` already
  uses, in a separate collection so a stored episode can never leak into
  retrieval results. Verified live: the same question rephrased a second
  time surfaced the first attempt's groundedness precedent as `memory_note`
  in the response, with no restart in between — see docs/CODE_NOTES.md for a
  real Chroma cross-process caching bug this surfaced and how it was fixed.

---

## Docs

| | |
|---|---|
| **[PROJECT_WALKTHROUGH.md](docs/PROJECT_WALKTHROUGH.md)** | **Start here.** Flowchart, how it was built step by step, how it runs |
| [CODE_QA.md](docs/CODE_QA.md) | 27 questions with answers about the code — why the grader is binary, why `no` parses before `yes`, why the fallback replaces documents instead of merging |
| [RESULTS.md](backend/eval/RESULTS.md) | Every measurement, including the negative ones |
| [INTERVIEW_NOTES.md](docs/INTERVIEW_NOTES.md) | Pitch, trade-offs, anticipated Q&A |
| [TECHNICAL_SPEC.md](docs/TECHNICAL_SPEC.md) · [CODE_NOTES.md](docs/CODE_NOTES.md) | Architecture, state schema, file-by-file notes |
| [RAG_FUNDAMENTALS.md](docs/RAG_FUNDAMENTALS.md) | RAG concepts, and an honest map of which pipeline stages this project skips |
| [ROADMAP.md](docs/ROADMAP.md) · [SETUP.md](docs/SETUP.md) | What was built when; environment setup |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Deploying to a HuggingFace Space, and the memory measurements that ruled Render out |

---

## What is not built

Stated rather than hidden — the System Status page says the same thing in the UI.

- **Deployment — the image is built and verified, the Space is not created yet.**
  `Dockerfile` at the repo root serves the API and the built SPA from one
  process; it ingests the corpus at build time and asserts the index is
  non-empty, because `vectorstore/` is gitignored and a fresh clone would
  otherwise boot empty. Verified locally: both routes answer, `indexed_chunks: 22`.
  Render was measured and ruled out — **698 MB peak against a 512 MB limit**, no
  persistent disk, and it sleeps. Target is a HuggingFace Space (16 GB);
  step-by-step in [DEPLOYMENT.md](docs/DEPLOYMENT.md).
- **The answer-correctness A/B.** Only the baseline arm ran — the treatment arm
  hit Groq's daily token cap. Whether reranking improves *answers* is still open.
- **The full 5k SciFact corpus + 300-query set.** Needs ~8 GB to Docker; this
  laptop gives 3.5. That run is what would settle the reranking question.
- No document upload API (ingestion is a deliberate offline step), no context
  filter, no prompt-injection defence. Each *query's own state* still runs
  independently (`CRAGState` carries nothing between requests) — but
  `app/memory/` now remembers *across* queries: episodic (has a similar
  question been asked before, and did its answer pass groundedness),
  semantic (a repeated failure pattern distilled into a fact). No long-term
  memory here, and that is stated rather than invented — this project has no
  client identity of any kind to scope one to. See
  [docs/CODE_NOTES.md](docs/CODE_NOTES.md).

122 tests, no API key needed: `.\dev.ps1 test`

---

Part of an **agentic self-correcting systems** portfolio theme alongside a
Self-Healing SQL Agent — same pattern (LLM + self-verification + autonomous
correction) applied to retrieval relevance rather than SQL execution errors.
