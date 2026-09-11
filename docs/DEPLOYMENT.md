# Deployment

Goal: one public URL, free, that runs **the pipeline the Evaluation page describes** —
hybrid retrieval and cross-encoder reranking included.

---

## What is left

The image is built and verified locally. These steps have to be done by hand:

- [ ] Create the Space (Step 2)
- [ ] Set `GROQ_API_KEY` in the Space's **Settings → Secrets** (Step 3)
- [ ] Push (Step 4) and wait for the build — first build is slow, it pulls two models
- [ ] Open the URL, run one local query and one web-fallback query (Step 5)
- [ ] Put the live URL in the README

Everything the code needed is done: the single-service image exists, CORS no longer
defaults to `*`, and the Chroma index is built into the image at build time.

---

## Why not Render

Render free gives 512 MB. Measured on the actual deploy image, `docker stats`:

| | Memory |
|---|---|
| Idle, after boot | 266 MB |
| After one local query | 686 MB |
| After a web-fallback query (**peak**) | **698 MB** |

That is **186 MB over the free limit**, and over Render's $7 tier too — it is also
512 MB. 2 GB starts at $25/month. Two other things break there independently:
no persistent disk, and the service sleeps after 15 minutes.

> **Note:** `ROADMAP.md` quotes 464 MB from an earlier measurement. The pipeline has
> grown since — hybrid retrieval, the cross-encoder, and SciFact support all landed
> after that number was taken. 698 MB is the current figure, measured on the image
> this guide deploys. The conclusion did not change, only the margin.

### "Just turn the reranker off so it fits"

Measured, then rejected:

| Config | idle | local query | web query (peak) |
|---|---|---|---|
| Hybrid + reranker **on** | 266 MB | 686 MB | **698 MB** |
| Hybrid + reranker **off** | 74 MB | 242 MB | **250 MB** |

It fits comfortably with the flags off. The reason not to: the System Status page
would then read *"Hybrid: off, Cross-encoder rerank: off"* while the Evaluation page
presents an A/B about exactly that pipeline. The live demo would not be running the
thing being measured. Turning off the best work in order to fit a smaller box is the
wrong trade.

---

## HuggingFace Spaces

16 GB RAM on the free tier, Docker support, no sleep, and persistent storage — an
ML demo's natural home.

### Step 1 — prerequisites (done)

| | |
|---|---|
| Single-service image | `Dockerfile` at the repo root — FastAPI serves the API *and* the built SPA |
| CORS | `CORS_ORIGINS` setting; default is the two local dev origins, not `*` |
| Vector index | built **into the image** at build time via `ingest.py`, then asserted non-empty |

The index is built rather than copied on purpose: `backend/vectorstore/` is gitignored,
so a fresh clone — which is what a Space builds from — has nothing to copy and would boot
with an empty index. `backend/data/` *is* in git, so the image can build the index itself,
and it can never drift from the corpus it represents.

### Step 2 — create the Space

[huggingface.co/new-space](https://huggingface.co/new-space) → **Docker** SDK → blank
template → free CPU hardware.

### Step 3 — the Space README

A Space is configured by YAML front matter in its own `README.md`. Create it in the
Space repo (not this one — this repo's README is for GitHub):

```yaml
---
title: Adaptive CRAG
emoji: 🔍
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---
```

`app_port: 7860` matches the `EXPOSE`/`CMD` default in the Dockerfile.

Then **Settings → Variables and secrets → New secret**: `GROQ_API_KEY`.

> Secrets go here, never in the Dockerfile and never in `.env.example` — that file is
> committed. A real key did once reach `.env.example` in this repo's history; it was
> purged and revoked, which is a lesson worth not repeating.

### Step 4 — push

```bash
git remote add space https://huggingface.co/spaces/<user>/adaptive-crag
git push space main
```

The first build takes a while: it installs dependencies, pulls the embedding and
reranker models (~100 MB), and runs the ingest. Subsequent builds reuse the layers.

### Step 5 — verify

```bash
curl https://<user>-adaptive-crag.hf.space/health
# {"status":"ok","indexed_chunks":22,...}   <- 22 is the check; 0 means ingest failed
```

Then in the UI run both routes, because they exercise different code:

| Question | Expected |
|---|---|
| *Why does chunk overlap matter when splitting documents?* | Local DB badge, `grade: yes` |
| *What is the current pricing of the Tavily search API?* | Web Fallback badge, `grade: no` |

Both were verified against this exact image locally — 15.9 s and 9.1 s respectively.

---

## Gotchas

- **Groq retires model ids.** `llama-3.3-70b-versatile` already 404s. Check before a demo:
  `curl https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY"`
- **Groq rate limits.** Under sustained load, call latency rises sharply — this is what
  made the eval's latency comparison unusable (see `backend/eval/RESULTS.md`). For a live
  demo, prefer the UI's fixed question chips over free-form typing.
- **`.env` is never committed**, and `.env.example` never holds a real key.
- **SciFact is not deployed.** The image ingests the `concepts` corpus only. SciFact
  needs the BEIR download and considerably more memory; its numbers ship as JSON that
  the Evaluation page reads, which is enough to show the results without running it.
