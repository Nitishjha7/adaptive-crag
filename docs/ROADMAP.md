# Roadmap

What exists, what does not, and what is next.

The *history* — the order things were built in and where the time actually went — is
in [BUILD_PLAN.md](BUILD_PLAN.md). This file is the current state.

---

## Built

| | |
|---|---|
| **Retrieval** | Chroma + BM25 fused by RRF, then a local cross-encoder reranker. Two corpora in separate collections, switched by `CORPUS` |
| **The corrective loop** | `retrieve → grade_documents → [conditional] → generate`, with `transform_query → web_search` on the correction path. Documents are **replaced**, not merged |
| **Guardrails** | An independent LLM groundedness check plus regex PII redaction, written in-house rather than pulling `guardrails-ai` |
| **API** | `POST /api/query` with the full node-by-node trace, `/api/stats`, `/api/documents`, `/health` |
| **Dashboard** | React + Vite + Tailwind — Chat, Documents, Evaluation, System Status. View lives in the URL hash, so refresh and back both work |
| **Eval harness** | `backend/eval/` — routing accuracy, fallback recall/precision, groundedness, per-route LLM call counts, retrieval recall@k, answer correctness |
| **Second corpus** | BEIR SciFact — 500 abstracts whose relevance labels ship with the dataset |
| **Tests** | 129, no API key required |
| **Streaming** | `POST /api/query/stream` — SSE, one progress event per graph node, phrased around the routing decision |
| **LLM gateway** | `get_llm()` — Groq → Groq `with_fallbacks()` chain, off by default, temperature preserved through the chain |
| **Token/cost tracking** | Per-query, per-model tokens and USD cost — the precise upgrade to the "3 vs 4 calls" proxy |
| **Monitoring** | `/metrics` (Prometheus: routing, groundedness, LLM calls/tokens/cost, fallback triggers) + JSON stdout logs |
| **CI** | GitHub Actions — tests, frontend build, and a deploy-image smoke test |
| **Deploy image** | Single-service `Dockerfile` at the repo root; ingests at build time and asserts the index is non-empty |
| **Cross-query memory** | `app/memory/` — episodic (similar past questions, retrieved by real vector similarity) and semantic (facts distilled from clusters of ungrounded episodes). Reuses the same FastEmbed/Chroma pair `retrieve` already loads, in a separate collection |

### Measured

| | concepts | SciFact |
|---|---|---|
| Routing accuracy | 20/20 | 22/28 (78.6%) |
| **Missed fallbacks** | **0** | **0** |
| Retrieval recall@k | no ground truth | 70% |
| Answer correctness | no ground truth | 83.3% (90.9% given gold retrieved) |
| Ambiguous-case route stability | 8/8 over 3 runs | — |

Two results came back **negative** and are published as such:

- **Hybrid + reranking moved nothing.** 27 of 28 concepts cases retrieved different
  chunks; zero routing decisions changed. On SciFact exactly one case changed, which
  is inside the noise of a 20-case set.
- **Latency could not be measured.** The first comparison looked convincing and turned
  out to be a Groq throttling artifact. The cost argument moved to LLM call counts
  (local 3, web 4), which follow from the graph's shape and reproduce exactly.

The most useful finding is not a score: **the grader made zero independent errors.**
On SciFact, every case whose gold document was retrieved routed correctly (13/13) and
every case that missed it fell back (7/7). Every apparent routing failure was a
retrieval miss the grader caught. The bottleneck is retrieval, not grading — and one
stage further down, given the right document the generator was right 10 times out of 11.

Full analysis: [backend/eval/RESULTS.md](../backend/eval/RESULTS.md).

---

## Not built

- **Deployment.** The image is built and verified; the Space is not created yet.
  See [DEPLOYMENT.md](DEPLOYMENT.md).
- **The answer-correctness A/B treatment arm** — stalled on Groq's daily token cap.
  Only the baseline arm has run, so whether reranking improves *answers* is open.
- **The full 5k SciFact corpus with a 300-query set** — needs roughly 8 GB of Docker
  memory against the 3.5 GB available here. That run is what would settle the
  reranking question.
- **Uploads are ephemeral.** A visitor's PDF is indexed into a session-scoped
  collection on the container filesystem, which Cloud Run recycles. Durable
  storage means object storage plus a hosted vector DB.
- **No long-term memory.** Episodic and semantic memory across queries shipped
  (`app/memory/`, see Built above). Long-term (per-client preferences, what
  the sibling Self-Healing SQL Agent scopes by `thread_id`) genuinely does
  not fit here: this project has no client identity of any kind — no cookie,
  no header, nothing beyond a bare question — and inventing one purely to
  check that box would be a fake feature, not a real one.
- **No prompt-injection defence** and no metadata/context filtering.

---

## Deployment plan

**Render was measured and rejected.** These are `docker stats` numbers on the deploy
image, not estimates:

| | Earlier (Phase 7) | Now (deploy image) |
|---|---|---|
| Idle, after boot | 266 MB | 266 MB |
| After one local query | 457 MB | **686 MB** |
| After a web query (**peak**) | 464 MB | **698 MB** |
| Image | 1.32 GB + 102 MB | 1.32 GB (single service) |

The figure changed but the conclusion did not: the earlier 464 MB predates hybrid
retrieval, the cross-encoder and SciFact support. At **698 MB against a 512 MB limit**
there is no headroom at all, where there used to be 48 MB. Render's $7 tier is also
512 MB; 2 GB starts at $25/month. Two further things break there regardless: no
persistent disk, and the service sleeps after 15 minutes.

### "Just turn the reranker off so it fits"

Measured, then rejected:

| Config | idle | local query | web query (peak) |
|---|---|---|---|
| Hybrid + reranker **on** | 266 MB | 686 MB | **698 MB** |
| Hybrid + reranker **off** | 74 MB | 242 MB | **250 MB** |

It fits comfortably with the flags off — the cross-encoder and BM25 index account for
most of the difference. The reason not to: the System Status page would then read
*"Hybrid: off, Cross-encoder rerank: off"* while the Evaluation page presents an A/B
about exactly that pipeline. The live demo would not be running the thing being
measured. Switching off the best work to fit a smaller box is the wrong trade.

**Deployed on [Google Cloud Run](https://adaptive-crag-906520260355.asia-south1.run.app)**
— `asia-south1`, 1 GiB, scale to zero.

| Piece | Where | Why |
|---|---|---|
| Whole stack, one image | Cloud Run | 1 GiB, scale to zero, free tier covers the usage |
| Vector DB | Chroma, **baked into the image** | 12 MB — no volume needed |
| LLM | [Groq](https://console.groq.com) | Free and fast. Key lives in Secret Manager |
| Web search | DuckDuckGo | No signup, no key |

The three prerequisites this needed — a single-service image, CORS no longer
defaulting to `*`, and the index built at image-build time — are **done**. Steps and
gotchas: [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Next

1. **Deploy.** The single biggest gap, and the only one that is not code.
2. **Re-run the SciFact A/B treatment arm** once Groq quota resets — one command.
3. **Harder eval cases.** Routing accuracy is pinned at 100% on concepts and cannot
   improve, so it cannot justify further retrieval work. The ambiguous tier was added
   for exactly this reason; it needs more cases where the corpus *half*-covers the
   question.
