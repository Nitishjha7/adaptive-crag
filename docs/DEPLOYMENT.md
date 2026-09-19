# Deployment

Goal: one public URL, free, that runs **the pipeline the Evaluation page describes** —
hybrid retrieval and cross-encoder reranking included.

---

## Live

**https://adaptive-crag-906520260355.asia-south1.run.app** — Google Cloud Run,
`asia-south1` (Mumbai), deployed from GitHub via Cloud Build on every push to `main`.

| Setting | Value | Why |
|---|---|---|
| Memory | 1 GiB | 489 MiB measured after a query, plus headroom |
| CPU | 1 | |
| Concurrency | 8 | each query holds the reranker in memory; 80 would exhaust 1 GiB |
| Min instances | 0 | scale to zero, so idle costs nothing |
| Max instances | 3 | caps the bill if the URL is shared |
| Request timeout | 300s | a web-fallback query runs ~8s; cold start is longer |
| Billing | Request-based | no background work outlives a response |

The only secret is `GROQ_API_KEY`, mounted from Secret Manager as an environment
variable. `SEARCH_PROVIDER=duckduckgo` needs no key, so the deploy has
one secret rather than two.

**Cold start is slow** — the image is 1.32 GB because the embedding model, the
cross-encoder and the Chroma index are all baked in at build time. That is the
trade for a first request that does not wait on a model download.

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

## Cloud Run, and what it cost in failures

The image and the sizing work above were done against a HuggingFace Space. Cloud
Run was chosen instead so that all three portfolio projects sit on one platform
with one billing account, one region and one set of console habits, rather than
three providers to keep alive.

The deploy itself is four steps — create the secret, point Cloud Run at the
GitHub repo, set the container limits, mount the secret — but two of them went
wrong in ways worth recording.

### The env var name is not the secret name

Cloud Run's secret form has two fields, and they are easy to conflate. The
resulting YAML was:

```yaml
- name: crag-groq-api-key        # env var name inside the container
  valueFrom:
    secretKeyRef:
      name: crag-groq-api-key    # the Secret Manager secret
```

The secret mounted correctly; it just arrived under the wrong name, so
`settings.GROQ_API_KEY` stayed empty. The revision was green, the container was
healthy, `/health` returned 200 — and every query returned a 500.

**What made it findable:** `/health` reports `groq_key_set` as a boolean. `false`
on a healthy container says the key is absent, not wrong — an invalid key would
have produced a 401 from Groq instead. The fix is `name: GROQ_API_KEY` on the
outer field.

### Health check path

This project serves `/health`, not `/api/health`. An HTTP startup probe pointed
at the wrong path fails a container that is working. The default TCP probe on
the container port is enough here and is what the service uses.
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
