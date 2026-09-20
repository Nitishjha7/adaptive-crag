# Build plan

[ROADMAP.md](ROADMAP.md) is what exists. [PROJECT_WALKTHROUGH.md](PROJECT_WALKTHROUGH.md)
is how the system works. This file is the *process*: the order things were built in,
the rule that decided that order, and — the part worth reading — where the time
actually went versus where it was expected to go.

---

## The rule that set the order

**Build the smallest thing that can be graded, then grade it, then decide what to
build next.**

The corpus came before the graph, because a controlled corpus with a *deliberate
gap* is what makes the fallback fire predictably instead of by luck. The eval
harness came before the retrieval work, because hybrid search and reranking are
the kind of change that feels like an improvement and has to be proved to
be one.

That ordering paid off twice, both times by returning a negative result:

- **Hybrid + cross-encoder reranking changed 27 of 28 retrievals and moved zero
  routing decisions.** Without the eval in place first, that would have shipped as
  an unexamined win.
- **The first latency comparison was a throttling artifact.** It looked convincing
  — local 13.7s vs web 18.5s — until the per-case timings showed everything after
  case 5 slowing down regardless of route. The cost argument moved to LLM call
  counts, which come from the shape of the graph and reproduce exactly.

---

## Order of execution

| # | Built | Why here |
|---|---|---|
| 1 | Controlled corpus + Chroma ingestion + config | Nothing downstream can be tested without an index, and the deliberate gap is what makes the fallback demonstrable |
| 2 | LangGraph skeleton — `CRAGState`, `retrieve`, `generate` | The smallest end-to-end path |
| 3 | `grade_documents` + conditional edge + `transform_query` + web fallback | The actual claim of the project |
| 4 | Output validation (groundedness + PII) | Small, deterministic, and it closes the "what if the model adds its own knowledge" question |
| 5 | FastAPI `/api/query` with step logs | Needed to exercise the graph from outside, and the trace is the demo |
| 6 | React dashboard — chat, trace timeline, Documents / Evaluation / System | A route decision nobody can see is not a feature |
| 7 | Docker Compose | One command to a working stack |
| 8 | **Eval harness** | Earliest point the routing claim could be checked rather than asserted |
| 9 | Ambiguity tier + hybrid retrieval + reranking | Only worth building once a metric existed that they could move |
| 10 | Second corpus (BEIR SciFact) | Labels that are not mine — the answer to "you wrote both the corpus and the test set" |
| 11 | Single-service deploy image | Last, because it should package a finished thing |

---

## Time-sinks — plan vs reality

| What was expected to hurt | What actually happened |
|---|---|
| **Guardrails AI setup** would be the biggest blocker | The library was never used. The fallback plan — a custom LLM groundedness check plus regex PII — took twenty minutes and added zero dependencies. It was the right call, and the interview point is identical |
| **Grader consistency** — the model would return explanations instead of a verdict | Never happened. `gpt-oss-120b` returns a clean `yes`/`no`. `parse_verdict` is still defensive, with 11 test cases, because the failure would be silent |
| **Fallback determinism** — live web results change between runs | Handled by the controlled corpus and its deliberate gap. The routing decision is stable even when the web text is not |
| **Embedding model download** (~100 MB) | Cached at Docker build time, so the first request is not the one that waits |

### The things nobody planned for

These are where the time actually went.

- **There is no Python on this machine** — only a WindowsApps stub. Everything runs
  in Docker; `dev.ps1` exists entirely because of this.
- **`llama-3.3-70b-versatile` does not exist on Groq any more** — a 404
  `model_not_found`. Listing `/v1/models` and switching to `openai/gpt-oss-120b`
  fixed it. **No mock would ever have caught this**, which is the argument for
  running against the real API before believing anything.
- **`ingest.py --reset` crashed inside Docker** — `vectorstore/` is a mount point,
  so `rmtree` hit `Device or resource busy`. Clearing the contents instead of the
  directory fixed it.
- **The first query after `docker compose up` returned 502** — `depends_on:
  service_started` let Nginx come up before uvicorn had bound. `service_healthy`
  fixed it.
- **SciFact caused two OOM kills** (exit 137) — 17,266 chunks do not fit in 3.5 GB.
  Ingestion now streams per batch, so peak memory no longer scales with corpus size.
- **SQLite lock contention with no error** — a running compose backend held the same
  `vectorstore/`, and the ingest simply hung for five minutes rather than failing.
  Large ingests need compose stopped first.
- **`--limit` could not truncate naively** — it cut gold documents, and the eval then
  showed those as *grader* failures when the fault was the corpus. Gold documents are
  selected first now, filler after; `test_corpus.py` asserts it.
- **A real Groq key reached `.env.example`** — that file is committed, `.env` is not.
  The key was revoked, purged from the history of all three repositories, and the
  remotes force-pushed. Verified afterwards from a fresh clone. The rule that came
  out of it: `.env.example` holds empty placeholders, never a value.

---

## How this was built

The code was written with heavy use of an AI coding assistant (Claude), working
phase by phase against the order above, with each phase run and verified against the
real Groq API and live search before moving on.

What that did **not** decide: which corpus to build and where to leave the gap, that
routing needed measuring rather than asserting, that a second corpus with
externally-supplied labels was necessary, that reranking had to be A/B'd behind a
flag, that the latency number was an artifact and had to be withdrawn, and that both
negative results belonged in the README rather than a footnote.

Those judgements, and the measurements that back them, are the project. They are
documented in [backend/eval/RESULTS.md](../backend/eval/RESULTS.md), which reports
what the evaluation does not support as carefully as what it does.

---

## What is left

1. **Deployment.** The single-service image is built and verified; the Space is not
   created yet. Steps in [DEPLOYMENT.md](DEPLOYMENT.md).
2. **The answer-correctness A/B treatment arm**, which stalled on Groq's daily token
   cap. One command once quota resets:
   `.\dev.ps1 eval -Corpus scifact --out eval/results_scifact.json`
3. **The full 5k SciFact corpus with a 300-query set** — needs roughly 8 GB of
   Docker memory against the 3.5 GB available here. That run is what would settle
   whether reranking helps answers rather than only retrieval.
