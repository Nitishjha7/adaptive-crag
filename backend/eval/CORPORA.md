# Two corpora, and why both exist

This project indexes one of two corpora, selected by `CORPUS`. They are not
alternatives — they answer different questions, and each is bad at what the
other is good at.

```powershell
.\dev.ps1 ingest -Corpus concepts   # default
.\dev.ps1 ingest -Corpus scifact    # BEIR SciFact
.\dev.ps1 ask -Corpus scifact "..."

# Poora stack (UI included) doosre corpus pe:
CORPUS=scifact docker compose up -d --build
docker compose up -d                        # wapas concepts pe
```

They live in **separate Chroma collections** (`crag_docs` / `crag_scifact`), so
switching never requires a re-ingest and the two can never contaminate each
other's retrieval.

---

## `concepts` — 7 hand-written docs, 22 chunks

RAG and agent-engineering concepts, written for this project.

**What it is good at: a predictable demo.** The gap is *categorical* by
construction — concepts in, vendor/pricing/news out — so the correction path
fires on demand rather than by luck. Every fixed demo query has a known route.

**What it is bad at: measuring retrieval.** Two problems, both documented in
[RESULTS.md](RESULTS.md):

1. **No ground truth.** Nothing says which chunk *should* have been retrieved,
   so retrieval quality cannot be scored at all. This is a large part of why the
   hybrid-search and reranker A/B came back flat — there was no metric that
   could respond.
2. **Single-author bias.** The same person wrote the documents, the eval
   questions, and the system. RESULTS.md says the honest fix is someone else
   writing the cases.

---

## `scifact` — BEIR SciFact

Scientific abstracts with claims and expert relevance judgments, from the
[BEIR](https://github.com/beir-cellar/beir) benchmark suite. Downloaded on
first use into `backend/beir/` (gitignored — it is a reproducible download, not
project source).

**What it is good at: making retrieval measurable.**

- **Labels are not mine.** `qrels/test.tsv` states which abstract supports which
  claim. `build_scifact_scenarios.py` turns those directly into `local` cases.
  That removes the bias above for the *hard half* of the eval.
- **Ground truth enables recall@k** — did the pipeline actually retrieve the
  gold document? This metric does not exist on the concepts corpus, and it is
  the one a reranker should be able to move.
- **Enough scale that ranking matters.** Thousands of abstracts instead of 22
  chunks, so which four survive to the grader is a real decision.

**What it is bad at: demoing.** The claims are dense biomedical text
(*"Mice defective for DNA polymerase I reveal increased mutation rates"*). It is
a benchmark, not a story — and the web-fallback half still has to be
hand-written, because no static scientific corpus can answer "what is Groq's
pricing today".

---

## The subset, and why it is not the first N documents

Ingesting all 5,183 abstracts produced 17,266 chunks and the container was
**OOM-killed** (exit 137) at 3.5 GB, twice. Two fixes:

1. Ingestion streams now — split and embed per batch of documents, so peak
   memory no longer scales with corpus size.
2. `--limit` takes a subset.

**But `--limit` is not truncation.** Taking the first N documents would silently
break the eval: gold documents sit anywhere in the file, and any that got cut
would leave a `local` case whose answer is genuinely not in the index. That
failure would show up in the eval as *the router being wrong*, when in fact the
corpus was wrong — the worst kind of measurement bug, because it blames the
wrong component.

So `load_corpus(limit=N)` keeps **every gold document first**, then fills the
remaining slots with non-gold documents. Filler matters: without it every
indexed document would answer some query and retrieval would be trivially easy.
This is the standard way to build a small retrieval benchmark, and
`test_corpus.py` asserts it.

---

## Running the full corpus — the run that is still owed

The 500-document subset is the honest limit of this laptop, not a design
choice. The reranking question — *does it actually help, or was the concepts
result the whole story?* — needs the full corpus and the full query set. On
SciFact-500 the A/B moved recall 65% → 70%, which is **one gold document out of
twenty**: the mechanism, not a magnitude.

What it needs: a machine that can give Docker roughly **8 GB** (17,266 chunks
were OOM-killed at 3.5 GB even after streaming was added), and a Groq tier that
will absorb ~600 graded queries without throttling.

The steps, in order:

```powershell
# 0. Stop the stack first - see the SQLite note below. This is not optional.
docker compose down

# 1. Full corpus. Drop --limit entirely; all 5,183 abstracts get ingested.
.\dev.ps1 ingest -Corpus scifact -Reset

# 2. Regenerate scenarios WITHOUT --limit, so every qrels claim is eligible.
#    With a subset, build_scifact_scenarios skips claims whose gold document
#    was not ingested; on the full corpus nothing is skipped.
.\dev.ps1 shell
#   > python -m eval.build_scifact_scenarios
#   > exit

# 3. Baseline arm - retrieval flags off.
.\dev.ps1 eval -Corpus scifact -Env USE_HYBRID=false,USE_RERANKER=false `
  --out eval/results_scifact_baseline.json

# 4. Treatment arm - flags on (the defaults).
.\dev.ps1 eval -Corpus scifact --out eval/results_scifact.json

# 5. Compare recall@k and routing accuracy between the two files.
```

`-Env` takes a comma-separated list and passes each entry through as `docker
run -e`. It exists because the A/B is this project's core workflow and there
was previously no way to run it except by hand-writing the full `docker run`
with all its mounts.

Three things to watch, all of which have already bitten this project:

- **Stop the compose stack before ingesting.** Both processes open the same
  embedded Chroma SQLite file. The second one does not error — it blocks. An
  ingest once ran five minutes with zero rows written and no message at all.
- **The scenarios file follows `CORPUS` automatically** (`scifact` →
  `scenarios_scifact.json`). It used to default to the concepts file no matter
  what, so `-Corpus scifact` would query the SciFact index with concepts
  questions and print confident, meaningless routing numbers — a failure that
  looks like the router being wrong when the setup was wrong. Override with
  `--scenarios` only if you mean to.
- **Do not shrink the query set to save rate limit.** The whole point of the run
  is a sample large enough to leave the noise band. Cutting back to 28 cases
  reproduces exactly the result that is already documented.

Until that run happens, the defensible claim stays: *the causal chain is real
and instrumented; the magnitude is unproven.*

---

## What each corpus can and cannot claim

| Claim | `concepts` | `scifact` |
|---|---|---|
| Routing accuracy | ✅ measured (20/20) | ✅ measured |
| Ambiguity / route stability | ✅ 8 hand-built cases | ❌ not built |
| **Retrieval recall@k** | ❌ **no ground truth** | ✅ from qrels |
| Labels written by someone else | ❌ | ✅ for `local` cases |
| Predictable live demo | ✅ | ❌ dense biomedical text |
| Corpus large enough that ranking matters | ❌ 22 chunks | ✅ |

Results are written per corpus — `results.json` and `results_scifact.json` — and
`/api/stats` reads whichever matches the active corpus. **Do not average them.**
They measure different things on different data.
