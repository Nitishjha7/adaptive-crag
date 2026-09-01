# Routing Eval — Results

Model: `openai/gpt-oss-120b` (Groq) · search: live DuckDuckGo · 20 labelled queries
· 3 runs

Run it yourself:

```powershell
.\dev.ps1 eval                  # full set, writes eval/results.json
.\dev.ps1 eval --limit 6        # smoke run
.\dev.ps1 eval --only web       # fallback cases only
```

---

## Headline

| Metric | Result |
|---|---|
| **Routing accuracy** | **20/20 (100%)** |
| — on the 5 `hard` cases | 5/5 |
| **Missed fallbacks** (expensive error) | **0** |
| Unnecessary fallbacks (cheap error) | 0 |
| Fallback recall / precision | 100% / 100% |
| Groundedness pass rate | 90–95% (varies by run) |
| **LLM calls per query** | **local 3.0 · web 4.0** |

Stable across three runs: routing was 20/20 every time. Groundedness moved between
90% and 95% — that variance is the guardrail, not the router (below).

---

## What this measures

Routing is a binary decision: every question should go `local` (the corpus in
`backend/data/` answers it) or `web` (it does not). `scenarios.json` labels all
20 from corpus coverage — each local case names the doc that covers it, each web
case states what is missing.

Plain accuracy is not enough, because the two errors cost wildly different things:

- **Missed fallback** — needed `web`, went `local`. The system answered from
  documents it judged sufficient when they were not. **This is precisely the
  hallucination CRAG exists to prevent.**
- **Unnecessary fallback** — needed `local`, went `web`. One extra search call.

So both are counted separately, and the exit code gates on **missed fallbacks
only** (`--max-missed-fallbacks`, default 1). A threshold belongs on the error
that is expensive, not on the average of the two.

**5 cases are marked `hard`** — the surface form points the wrong way. #12 asks
for a specific model's dimension count (sounds like vendor docs, is in the
corpus); #19 asks which vector DB companies raised funding (retrieves doc 03
strongly, and doc 03 answers a different question). Easy cases inflate a score;
these are the ones that test the grader.

---

## Read honestly: 100% means the task is easy, not that the router is perfect

A perfect score on 20 cases is a reason to look harder, not to celebrate.

The corpus gap is **clean by construction**. `backend/data/` holds RAG/agent
*concepts* and deliberately no vendor, pricing, version or news material. So
almost every web case differs from the corpus along an obvious axis — "current",
"pricing", "newest", "released" — and the grader has a strong, almost lexical
signal to work with.

**What this eval supports:** on a corpus whose gap is categorical, the grader
routes correctly, including when surface features point the wrong way.

**What it does not support:** any claim that routing survives an *ambiguous* gap
— where the corpus covers a topic partially, or is subtly out of date. That is
the harder and more realistic case, and this set does not contain it.

**To make this eval actually hard,** add cases where the corpus half-answers the
question: doc 05 mentions Self-RAG in a single line — is that sufficient to
answer "how does Self-RAG differ from CRAG"? Reasonable people would disagree,
which is exactly what makes it a real test. Those cases were left out because
ambiguous labels make a metric meaningless, not because they do not matter.

**Not tuned against.** The cases were written from corpus coverage before the
first run, and no prompt was changed in response to the results. (Contrast with
Code Guardian's routing eval, where the tool docstrings *were* tuned against the
set and the README says so.) That said, one author writing both the corpus and
the eval is its own bias — the honest fix is someone else writing cases.

---

## The cost argument, and the measurement that failed

The design claims adaptive routing is cheaper than always searching. The eval
tries to put a number on that, and the first attempt was wrong.

**LLM calls per query — this is the number that holds:**

| Route | Nodes calling the LLM | Calls |
|---|---|---|
| local | `grade_documents`, `generate`, `validate_guardrails` | **3.0** |
| web | `grade_documents`, `transform_query`, `generate`, `validate_guardrails` | **4.0** |

Correction costs **one extra LLM call plus one web round trip — about 33% more
LLM calls** on the queries that need it, and nothing at all on the queries that
do not. Always-search would pay that on every query. This number is exact by
construction: it comes from the graph's shape, so it reproduces every run.

**Latency, however, could not be measured here — and finding that out was the
useful part.**

The first run went case-by-case in file order: all 12 local cases, then all 8
web. Result: `local 13.7s vs web 18.5s`, which looks like a clean win for the
local path. It was an artifact. The per-case timings show cases 1–4 at 2–8s and
**everything from case 5 onward at 15–22s regardless of route** — Groq throttling
under sustained load, and because local cases ran first, the entire slowdown
landed in the local bucket while the fast early cases inflated nothing else.

`interleave()` (now the default ordering) alternates local and web so throttling
falls on both buckets equally. Re-run interleaved: `local 16.2s vs web 14.9s` —
the web path apparently *faster* than local, which is structurally impossible
since it does strictly more work. Both numbers are noise. At this scale
throttling swamps the route difference entirely.

So latency is still printed, but labelled as not a route signal. **The cost
argument rests on call counts, which are exact, not on latency, which this setup
cannot measure.** A real latency comparison needs a dedicated paid-tier run with
warm-up and repeated trials — worth doing, not done here.

---

## Groundedness: one consistent false positive

The guardrail flagged 1–2 answers per run. They are not the same kind of flag:

**Case #1 — false positive, every run.** *"Why is cosine similarity used instead
of Euclidean distance?"* The answer says cosine *"measures the angle between
vectors and ignores their magnitude"* — which is near-verbatim from
`01_vector_embeddings.md`. It is grounded, and the checker said it was not.
Flagged in all three runs, so this is systematic, not sampling noise.

**Case #20 — likely a true positive.** *"What is the context window of the newest
Claude model?"* went to web and answered "1 million-token". If that figure was
not in the DuckDuckGo snippets, the model supplied it from its own training —
exactly what the groundedness check is for, and exactly what it caught.

The design already handles this the right way: a flagged answer is **shown with a
warning, not hidden** (`test_ungrounded_answer_is_flagged_not_hidden`). A false
positive therefore costs a caution banner, not a lost answer — the cheap
direction to err in.

Still, **90–95% is the guardrail's ceiling here, and roughly half of the misses
look like false positives.** That is a real limitation and it is separate from
routing quality. A stricter groundedness prompt, or scoring per-claim instead of
per-answer, would be the next thing to try.

---

## Per-run summary

| Run | Order | Routing | Missed fallbacks | Groundedness |
|---|---|---|---|---|
| 1 | file (local-then-web) | 20/20 | 0 | 95% |
| 2 | interleaved | 20/20 | 0 | 95% |
| 3 | interleaved | 20/20 | 0 | 90% |

Per-case output for the last run is in [`results.json`](results.json).

**This eval is not deterministic.** Web cases hit live DuckDuckGo, and the LLM is
not perfectly stable even at temperature 0. A ±1 case difference between runs is
normal, which is why no headline figure here carries a decimal.
