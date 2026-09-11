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

**That gap has since been filled — see the next section.**

---

## The ambiguous tier: measuring stability instead of correctness

Eight cases (IDs 21–28) were added where the corpus **half-covers** the topic.
Each names the exact passage that makes it arguable, in `disagreement`.

They are deliberately **not scored for correctness.** Their labels are genuinely
contestable, and folding a contestable label into routing accuracy would make the
headline number undefendable — which is the reason they were excluded in the
first place. Adding them by inventing a "right" answer would have recreated the
original problem, not solved it.

Instead they are scored for **stability**: run the same question three times
(`--repeat 3`) and check whether the router picks the same side every time.
*Which* side it picks is a judgement call. Flipping between sides on identical
input is not — that is non-determinism, and it is a defect regardless of which
label you prefer.

This also gives future retrieval work something to move. Routing accuracy is
pinned at 100% and cannot improve, so a reranker or hybrid search could be added
but never justified. Stability on half-covered cases can.

### Result

| | |
|---|---|
| Ambiguous cases | 8 |
| **Route stability** (3 runs each) | **8/8 — 100%** |
| Split | 4 local · 4 web |

Two readings, and the second is the useful one.

**The grader is deterministic even where the question is not.** Twenty-four runs,
zero flips. Temperature 0 plus a one-word output is doing its job.

**But determinism is not consistency of reasoning.** Compare these two:

| Case | Question | Route |
|---|---|---|
| #25 | Does the 10-15% chunk overlap guidance also apply to **source code files**? | **web** |
| #28 | Is 800 characters a good chunk size for long **legal contracts**? | **local** |

These are the *same question shape*: the corpus states a general guideline, the
question asks whether it holds for a named domain the corpus never mentions. The
grader routes them oppositely, and does so stably.

So the honest reading of 100% stability is: **the grader applies *a* rule
reliably, not necessarily a coherent one.** Per-question determinism is real and
worth having; a consistent principle across structurally identical questions is
not demonstrated. That is a sharper and more useful finding than the headline
number, and it is exactly the kind of thing a reranker experiment could now be
tested against.

**The 4/4 split matters too** — it confirms these cases are genuinely ambiguous
rather than secretly easy. Had all eight fallen the same way, the tier would be
measuring nothing.

**Not tuned against.** The cases were written from corpus coverage before the
first run, and no prompt was changed in response to the results. (Contrast with
Code Guardian's routing eval, where the tool docstrings *were* tuned against the
set and the README says so.) That said, one author writing both the corpus and
the eval is its own bias — the honest fix is someone else writing cases.

---

## Hybrid retrieval and reranking: a clean negative result

Hybrid search (vector + BM25, fused with RRF) and cross-encoder reranking were added
last, deliberately — after the ambiguity tier existed, so there was a metric that
*could* move. Both sit behind `USE_HYBRID` / `USE_RERANKER`, and the same 44 runs
were executed with them off and on.

| Metric | Baseline (vector only) | Hybrid + rerank |
|---|---|---|
| Routing accuracy | 100% (20/20) | 100% (20/20) |
| Missed fallbacks | 0 | 0 |
| Unnecessary fallbacks | 0 | 0 |
| **Ambiguous route stability** | **100% (8/8)** | **100% (8/8)** |
| Ambiguous split | 4 local · 4 web | 4 local · 4 web |
| Groundedness pass | 85% | 90% |

**Every one of the eight ambiguous cases took the same route in both configurations,**
including the #25/#28 incoherence described above. It survives reranking unchanged.

Groundedness moved 85% → 90%, which is one case out of twenty and sits inside the
run-to-run range this document already reports (85–95%). It is not evidence.

### The retrieval genuinely changed — the decision did not

The obvious objection is that the flags did nothing. They did:

| Comparing top-4 across all 28 cases | |
|---|---|
| Identical chunks, identical order | **0** |
| Same chunks, reordered | **1** |
| **Different chunks retrieved** | **27** |

So 27 of 28 questions were answered from a *different* set of chunks, and the routing
decision was identical on every single one.

### Why — and this is the useful part

**The corpus is small and topically clustered.** With 22 chunks and k=4, any reasonable
retriever surfaces chunks from the right document. Whether the grader sees chunking
chunks 1,2,4,7 or 2,3,4,9, the signal it reads is the same: *this material is about
chunking*. The verdict follows from topic, not from ranking quality.

**And the grader does not consume order.** `grade_documents` joins all four chunks into
one prompt. Reranking optimises *ordering*, but ordering is invisible to a node that
concatenates. Reranking can therefore only change the outcome by changing *membership* —
and on a 22-chunk corpus, membership changes rarely cross a topic boundary.

**Reranking is not useless — it is aimed at the wrong metric here.** It should help the
*answer* (which passages the model writes from), and this eval does not measure answer
quality. It measures routing. Those are different axes, and the honest conclusion is that
this eval cannot show a benefit rather than that no benefit exists.

### What this changes about the claim

Do not say "I added hybrid search and reranking and it improved retrieval." The defensible
version:

> "I added them last, on purpose, because until the ambiguity tier existed there was no
> metric that could respond. Then I A/B'd them and got a negative result — 27 of 28
> questions retrieved different chunks and not one routing decision changed. On a
> 22-chunk topically-clustered corpus the grading decision is dominated by topic-level
> signal, and the grader concatenates chunks so it never sees the ordering the reranker
> optimises. To show a benefit I would need a larger corpus, and an answer-quality metric
> rather than a routing one."

That is a better answer than a fabricated improvement, and it is the second negative
result in this file — see the latency section below for the first.

---

## SciFact: the same A/B, on a corpus that can answer the question

The concepts-corpus result above ended in *"this eval cannot show a benefit"* rather
than *"there is none"*. Two things were blocking it: no ground truth about which
chunk should have been retrieved, and only 22 chunks. BEIR SciFact fixes both —
1,717 chunks and expert `qrels`, so **recall@k** exists as a metric at all.

Same 28 cases, run with the flags off and on.

| Metric | Baseline (vector only) | Hybrid + rerank |
|---|---|---|
| Routing accuracy | 75.0% (21/28) | **78.6% (22/28)** |
| **Retrieval recall@k** | **65.0%** | **70.0%** |
| Unnecessary fallbacks | 7 | **6** |
| Missed fallbacks | **0** | **0** |
| Groundedness | 89.3% | 92.9% |

**Everything moved in the right direction, and the mechanism is visible per case:**
exactly one case changed — **#10**, whose gold document went `MISS → gold`, and whose
route followed `web → local`. Recall improved; routing improved by precisely the case
recall fixed.

### Read this honestly: one case is not a result

+5pp recall on 20 gold-bearing cases **is one document**. On a sample this size that
is well inside noise, and it would be dishonest to present 65% → 70% as a reliable
improvement. What this run establishes is narrower and more useful:

- **The causal chain is real and observable.** Better retrieval → gold document found
  → grader says local → routing correct. That chain was invisible on the concepts
  corpus and is now instrumented end to end.
- **The earlier negative result's explanation holds up.** It said the concepts corpus
  could not show a benefit because it had no recall to measure. Give the same code a
  corpus with ground truth and the metric moves. The explanation predicted the result.

To claim reranking actually helps, this needs the full 5k-document corpus and the full
300-query test set, not 20 cases on a 500-document subset. That run needs more RAM than
this laptop gives Docker — the honest limit, stated rather than hidden.

### The finding that matters more than the delta

On the baseline run, the correlation between retrieval and routing was **perfect**:

| Gold document | Cases | Route taken | Routed correctly |
|---|---|---|---|
| Retrieved | 13 | local | **13 / 13** |
| Missed | 7 | web | 0 / 7 |

**The grader made zero independent errors.** Every single routing "failure" was a
retrieval miss that the grader detected correctly — it looked at four chunks that did
not contain the answer and said so. That is the grading node doing exactly its job.

Which means **75% routing accuracy understates the grader**. Conditional on what it was
given, it was right 20 out of 20. The bottleneck on this corpus is retrieval, not
grading — and that reframes where further work should go.

It also explains why `missed_fallbacks` stayed at **0** in both runs. The expensive
error — answering locally from documents that cannot support the answer — never
happened. The router failed only in the cheap direction.

---

## Answer correctness — the metric this eval was missing

Every number above measures the *route*. Routing accuracy, recall@k, missed and
unnecessary fallbacks — all of them ask "did the system look in the right
place?". Groundedness is the one answer-level check, and it only asks whether
the answer is consistent with whatever context it was handed: **an answer built
from the wrong documents can pass groundedness while being wrong.**

That gap was named in the reranking section above — *"it should help the
answer, and this eval does not measure answer quality"* — and left open. This
closes it.

### Where the ground truth comes from

SciFact is a claim-verification dataset. `queries.jsonl` carries, for each
claim, whether the gold abstract **SUPPORTS** or **CONTRADICTS** it. That is the
dataset's own label, written by its authors, not a judgement of mine and not an
LLM's opinion.

12 of the 20 local cases carry such a label. Queries whose gold documents
disagree with each other are skipped — on mixed evidence there is no honest
right answer to score against.

**This is deliberately not an LLM-as-judge setup.** An LLM judge is asked "is
this answer good?", which is the model's opinion standing in for a measurement.
Here the model is asked only to *read*: what position does this text take on the
claim? Right and wrong are decided by the dataset. The extraction is still the
weak link in the chain — one misread flips one case — and a wrong reading is
indistinguishable from a wrong answer in the score. `answer_verdict.py` says so
in its docstring, and its parser has its own tests, including the trap that
`"does not support"` contains the substring `support`.

### Baseline result (vector-only retrieval, 28 cases)

| | |
|---|---|
| Answer correctness, end to end | **83.3%** (10 / 12) |
| Answer correctness, **given the gold document was retrieved** | **90.9%** (10 / 11) |
| Answers that took no position at all | 1 |

Only two cases were scored wrong, and they fail in completely different ways:

- **#10** — the gold document was **never retrieved**. The system did not invent
  a verdict; it took no position (`UNCLEAR`). Counted wrong because the dataset
  says CONTRADICT, but the failure is retrieval's, and the generator's behaviour
  on missing evidence was the correct one: say nothing rather than guess.
- **#11** — the gold document **was** retrieved and the answer still reached the
  opposite conclusion. This is the one genuine generator error in the run.

### What that adds to the earlier finding

The routing section above established that **the grader made zero independent
errors**: every routing failure was a retrieval miss it detected correctly. This
run extends the same shape one stage further down the pipeline — given the right
document, the generator was right **10 times out of 11**.

So two of the three stages are close to clean on this corpus, and both of the
remaining failures trace back to the same place. **Retrieval is the bottleneck,
and now that is measured at every stage rather than inferred from routing
alone.**

### The A/B on this metric is NOT done — and that is the point of the metric

The reranking question was always *"does better retrieval produce better
answers?"*. Answering it needs both arms. **Only the baseline arm has run.** The
treatment arm (hybrid + reranker on) died partway through on Groq's daily token
cap:

    RateLimitError: 429 - tokens per day (TPD): Limit 200000, Used 199876

so `results_scifact.json` is still a previous run that predates this metric and
carries no `answer_verdict` field at all. Nothing in this document or the
dashboard compares the two on answer correctness, because there is nothing to
compare yet.

To finish it, after the daily quota resets:

```powershell
.\dev.ps1 eval -Corpus scifact --out eval/results_scifact.json
```

and compare `answer_verdict_given_gold_pct` between the two files. That subset is
the one to watch: it holds retrieval constant, so it isolates whether reranking
changed what the model actually wrote.

### One more thing this run showed, for free

Groundedness came out at **78.6%** here. The previous baseline run — same
config, same 28 cases — reported **89.3%**. That is a 10-point swing from
run-to-run variation alone, roughly three cases. It is a useful calibration on
every small number in this document: **differences of a few points on 28 cases
are noise, and this project's rule is to say so rather than to pick the
favourable run.**

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
