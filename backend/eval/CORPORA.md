# Two corpora, and why both exist

This project indexes one of two corpora, selected by `CORPUS`. They are not
alternatives — they answer different questions, and each is bad at what the
other is good at.

```powershell
.\dev.ps1 ingest -Corpus concepts   # default
.\dev.ps1 ingest -Corpus scifact    # BEIR SciFact
.\dev.ps1 ask -Corpus scifact "..."
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
