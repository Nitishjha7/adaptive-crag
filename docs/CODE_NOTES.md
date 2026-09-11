# Code Notes — what each file is for

Every file and dependency, with the reason it exists. Phases 1–10 are done (eval
harness, citations, hybrid retrieval + reranking, BEIR SciFact corpus). Deployment is
the remaining gap.

---

## backend/requirements.txt

| Package | What it does | Why it is here |
|---|---|---|
| `langgraph` | Stateful agent graph — nodes and conditional edges | The core of CRAG. A simple chain cannot express conditional branching (relevant → generate, otherwise → fallback); that needs a graph |
| `langchain` / `langchain-core` | LLM abstractions, prompt templates, output parsers | Grading, rewriting and generation are all prompt chains. Swapping providers stays easy |
| `langchain-groq` | Groq LLM binding | Free tier and very fast inference — a small call like grading is latency-sensitive |
| `chromadb` | Embedded vector database | The local knowledge base. Zero infrastructure, persists to a Docker volume |
| `fastembed` | Lightweight local embedding models (ONNX) | No API key, works offline, fast. Lighter than pulling HuggingFace transformers |
| `tavily-python` | Tavily Search API client | **Optional upgrade** (`SEARCH_PROVIDER=tavily`). Gives LLM-optimised snippets rather than raw HTML, but needs a signup |
| ~~`guardrails-ai`~~ | — | **Not used.** The hub download and version pinning were a time-sink; a custom LLM groundedness check plus regex PII does the same job with zero dependencies. See `validators.py` below |
| `ddgs` | DuckDuckGo search client | **The default web search provider — no API key needed.** The project runs from day one |
| `rank-bm25` | BM25 keyword scoring | The other half of hybrid retrieval. Vector search is weak on exact tokens; BM25 is strong there. The reranker came with `fastembed` — **no new dependency** |
| `langchain-text-splitters` | `RecursiveCharacterTextSplitter` | Splits on paragraph and heading boundaries rather than a fixed character count |
| `fastapi` | ASGI web framework | The `/api/query` gateway. Async-native, automatic `/docs` |
| `uvicorn[standard]` | The ASGI server | FastAPI is not a server by itself |
| `pydantic` / `pydantic-settings` | Validation and typed config | Request/response models; typed settings from `.env` |
| `python-dotenv` | Loads `.env` in dev | Local environment variables |

---

## backend/app/config.py

Central configuration and factory functions. No business logic.

- `Settings(BaseSettings)` — `GROQ_API_KEY`, `TAVILY_API_KEY`, model names, `TOP_K`,
  chunk parameters, `CORS_ORIGINS`, paths. Loaded from `.env` at the repo root, which
  is the same file docker-compose reads.
- `get_llm(temperature=0.0)` — a configured `ChatGroq`, with a clear error if the key
  is missing.
- `get_embeddings()` — `FastEmbedEmbeddings` (local ONNX, no API call).
- `get_vectorstore()` — a handle to the persisted Chroma collection.

**Why factories rather than direct imports:** they are easy to mock in tests (the
Phase 2 wiring test ran with `get_llm` replaced by a fake, with no Groq key at all),
and swapping a model happens in one place.

**Why `@lru_cache`:** every node imports config. Without caching, each call would
re-parse `.env` and load a fresh embedding model — slow and pointless.

**Why `ChatGroq` / `FastEmbedEmbeddings` are imported inside the functions:** it keeps
module import cheap. Running something like `python -m app --help` does not pull in
heavy ML dependencies.

---

## backend/data/ — the controlled corpus

Seven markdown documents covering RAG and agent engineering **concepts** — embeddings,
chunking, vector databases, naive-RAG failure modes, CRAG, query transformation, agent
graphs and state.

**The deliberate gap:** no product, pricing or vendor detail, no recent releases, and
**zero mention of MCP**. That gap is what makes the correction path trigger
predictably, so the demo does not depend on live randomness.

**Why real topics rather than a fictional company:** a fictional corpus would still
produce `grade: no`, but the web search would then return nothing useful and the
second half of the demo would die. The gap has to be **genuinely answerable from the
web**.

Fixed demo queries and their expected routes are in `backend/data/README.md`.

---

## backend/ingest.py

Documents → chunks → embeddings → Chroma.

- `load_documents()` — reads `data/*.md|txt`, skipping `README.md` (it is notes
  *about* the corpus; ingesting it would inject "what is not in here" meta-text that
  confuses the grader).
- `split_documents()` — `RecursiveCharacterTextSplitter`, 800/100, with `\n## ` first
  in the separator list so splits land on heading boundaries.
- **Idempotent** — skips when the collection is already populated. `--reset` wipes and
  rebuilds.

**A real bug found here:** `--reset` used to call `shutil.rmtree(store_dir)`. Inside
Docker, `vectorstore/` is a **mount point**, and removing it raises `OSError: Device
or resource busy`. The fix is to clear the directory's **contents**, not the directory.

---

## backend/app/__main__.py

`python -m app "question"` invokes the graph without FastAPI and prints the full
trace. The API exists, but this is still the smallest debugging loop: one process, one
invoke, one complete trace.

---

## dev.ps1 (repo root)

There is no Python installed on the machine this was built on — everything runs in
Docker. This helper wraps the long `docker run` incantation: `build` / `ingest
[-Reset]` / `ask "..."` / `test` / `eval` / `serve [-Port N]` / `shell`.

Source is **bind-mounted** (`app/`, `data/`, `eval/`, `ingest.py`), so an edit needs no
rebuild — the image only supplies dependencies. `.env` is injected with `--env-file`
rather than baked into the image.

`docker compose up` runs the full stack; `dev.ps1` remains the backend-only loop,
which is faster to iterate in.

---

## backend/tests/ — 75 tests, `.\dev.ps1 test`

| File | What it covers |
|---|---|
| `conftest.py` | The `fake_llm` and `fake_search` fixtures (via monkeypatch, so they undo themselves after each test) |
| `test_routing.py` | Both routes, documents being replaced, search failure, malformed grader output |
| `test_grading.py` | The 11 cases of `parse_verdict` |
| `test_validation.py` | PII redaction, false positives, ungrounded flagging, fail-open |
| `test_api.py` | `/health`, 422 validation, response shape |
| `test_retrieval.py` | BM25, the RRF fusion maths, reranker fallback, retrieval flags |
| `test_corpus.py` | Collection isolation, the BEIR subset gold-document guarantee, qrels score-0 filtering |
| `test_answer_verdict.py` | Reading a SUPPORT/CONTRADICT stand out of an answer |

**Why no real LLM calls in the tests:** these test **control flow**, not model quality.
Real calls are slow, cost money, need a key and are non-deterministic — that is, flaky
in CI. Giving the grader a scripted verdict is exactly the thing under test: *"if the
grader says 'no', does the graph take the right path?"* The grader's **accuracy** is a
different question, and it belongs to the eval harness, not here.

**The most important test:** `test_fallback_replaces_local_docs_instead_of_merging`. If
rejected local documents survived alongside the web snippets, the whole point of CRAG
would be gone — and that can break silently, so it is asserted.

---

## backend/app/schemas/crag_state.py

`CRAGState` is a TypedDict and the graph's single source of truth. Each node returns a
partial update to it.

- `question` — the original, never mutated.
- `transformed_query` — set only by the `transform_query` node.
- `documents` — **overwrite** semantics (no reducer). `retrieve` sets it,
  `web_search_fallback` **replaces** it. An additive reducer is *deliberately* absent:
  appending would leave rejected local documents in context alongside the web
  snippets, which is the hallucination risk the grading step exists to remove.
- `relevance_score` — `"yes"` / `"no"`; the conditional edge routes on it.
- `source_type` — `"vector_db"` by default, `"web_search"` after a fallback. Drives the
  UI badge.
- `generation` — the raw LLM answer.
- `final_output` — the guardrail-validated answer; this is what the user sees.
- `logs` — each node appends one line (`Annotated[list, operator.add]`). The trace
  viewer renders this.

---

## backend/app/graph/build_graph.py

Graph wiring — register nodes, define edges, `compile()`.

### The shape

- `START → retrieve → grade_documents`.
- A conditional edge on `grade_documents`: `relevance_score == "yes"` → `generate`,
  otherwise → `transform_query`.
- `transform_query → web_search_fallback → generate`.
- `generate → validate_guardrails → END`.

**Why a graph and not a chain — visible here:** which node runs after
`grade_documents` is not fixed at compile time; it is decided at runtime by reading
state. A linear chain cannot express that.

**Why `decide_to_generate` is its own function:** separating routing logic from grading
logic means both can be tested independently. The function is deliberately trivial —
the entire decision happens in `grade_documents`, and this only reads the result.

**Why it defaults to `transform_query` rather than `generate`:** if `relevance_score`
ends up empty for any reason, the safe direction is the correction path — pay for one
extra web call rather than answer from unverified context.

**Design choice:** the fallback branch merges back into the same `generate` node rather
than a second one. `generate` only reads `state["documents"]`, so the source makes no
difference to it.

---

## backend/app/nodes/retrieve.py

The graph's entry point. **No relevance decision happens here** — similarity search
always returns k results, whether or not anything in the corpus is relevant. That is
naive RAG's core failure mode; the decision belongs to `grade_documents`.

Pipeline:

```
vector search (8)  ─┐
                    ├─ RRF fusion ─→ cross-encoder rerank ─→ top 4
BM25 search (8)    ─┘
```

- Populates `documents` and `sources`, sets `source_type = "vector_db"`.
- Every stage shows in the log:
  `retrieve -> 4 chunks (vector=8, bm25=8, fused=12, reranked 12->4)`.

**Why `RETRIEVAL_CANDIDATES` (8) exceeds `TOP_K` (4):** otherwise the reranker has
nothing to choose between and becomes a no-op.

**Why both stages sit behind flags (`USE_HYBRID`, `USE_RERANKER`):** not for
configurability. It is so the **eval can turn them off and compare against a
baseline**. In this project a feature is not a feature until its benefit can be shown
— and since routing accuracy is pinned at 100%, these are judged on the stability of
the ambiguous cases instead. The A/B result is in `eval/RESULTS.md`.

---

## backend/app/nodes/grade_documents.py

**Core decision #1.** An LLM binary relevance grader.

- The prompt is tight — "answer with a single word: yes/no, do not explain".
- Parsed defensively, checking `no` before `yes`, because the model occasionally adds
  text.
- Temperature 0 — this needs consistency, not creativity.
- Returns only `relevance_score` and `logs`.

**The point:** this is one small, cheap classifier call made *before* generating a full
answer. That is the difference from naive RAG — verify before trusting.

---

## backend/app/nodes/transform_query.py

Rewrites a natural-language question into a keyword-focused web search query.

User questions are conversational ("I'd like to understand how..."), and search engines
do better with keywords. The rewrite lands in `transformed_query`, which
`web_search_fallback` consumes.

---

## backend/app/nodes/web_search_fallback.py

**Core decision #2.** Live web context.

- Searches with `transformed_query` (falling back to the original question).
- **Replaces** `documents` with the result snippets — the local ones were graded
  irrelevant, so keeping them has no upside.
- Sets `source_type = "web_search"` for the badge and the logs.

**Why replace rather than merge:** the local documents have already been graded `no`.
Keeping them dilutes generation and reintroduces the hallucination risk the grading
step exists to remove.

---

## backend/app/nodes/generate.py

Final answer synthesis.

- Prompt: "answer ONLY from the provided context; if the context is insufficient, say
  so".
- Joins `state["documents"]` into context — local or web, it makes no difference here.
- Writes to `generation` (raw, not yet guardrail-checked).

---

## backend/app/nodes/validate_guardrails.py

The graph's last safety net, and the node that fills `final_output`.

- Calls `validate_answer(answer, context, question)` from `guardrails/validators.py`.
- Logs `validate_guardrails -> pass=True/False (reason)`.

**Why this node, when `generate`'s prompt already says "only from context":** a prompt
is a request, not a guarantee. The model can quietly add its training knowledge. This
node is a second, *independent* look at the answer.

---

## backend/app/guardrails/validators.py — custom, **not** Guardrails AI

> **Decision (Phase 4):** the `guardrails-ai` library was not used. Its hub-based
> validator download and version pinning were the project's biggest time-sink, and what
> matters in an interview is not the library's name but understanding why and how a
> final answer should be verified. Two small checks do the same job with zero extra
> dependencies. The ROADMAP had written this fallback plan in advance; it was taken.

Two checks:

1. **Groundedness (an LLM call)** — "is every claim in this answer supported by the
   context? yes/no". Temperature 0, reusing the same defensive `parse_verdict` as the
   grader, so the two parsers cannot drift apart.
2. **PII (regex)** — email, card, SSN, international phone. **Deliberately regex, not an
   LLM:** PII detection should be deterministic, and another LLM call adds latency
   without a reliable gain.

**Why toxicity was left out:** the input is a controlled corpus plus search snippets,
and an LLM "is this toxic" check without a proper classifier is theatre. Between naming
a capability and not verifying it, and not naming it — the second is better.

### Two decisions worth being able to defend

**An ungrounded answer is flagged, not blocked.** A warning prefix is added; the answer
is not hidden. In a demo, showing a hallucination *being caught* is more convincing
than making it disappear — and for a user, "this might be wrong" beats a blank screen.
**PII is different** — it is redacted, because flagging while displaying is still the
leak.

**The groundedness check fails open, not closed.** If the check itself crashes (network,
rate limit), blocking the answer would be wrong — that answer was built from already
verified context. On an exception it assumes grounded and notes it in the log. Failing
closed would let one flaky call turn the whole system into "I can't tell you anything".

---

## backend/app/tools/beir_loader.py — the second corpus

Downloads and parses BEIR SciFact. Full comparison in
[eval/CORPORA.md](../backend/eval/CORPORA.md).

**Why a second corpus was needed.** The seven documents in `backend/data/` have two
problems, both written up in RESULTS.md:

1. **No ground truth.** Nothing records which chunk was *correct*, so retrieval quality
   could not be measured at all. That is the main reason the hybrid + reranker A/B came
   back flat — there was no metric available to move.
2. **Single-author bias.** I wrote the documents and I wrote the eval labels. RESULTS.md
   says outright that the honest fix is someone else writing them.

BEIR fixes both: `qrels/test.tsv` carries expert relevance judgements about which
abstract supports which claim. **Those labels are not mine.**

**Why not the `datasets` library:** BEIR's official zip downloads directly and the
format is three plain JSONL/TSV files. `datasets` would drag in a large dependency tree
including pyarrow, to read three files.

**Why `load_qrels` drops score 0:** in BEIR, 0 means "judged, and not relevant".
Treating it as gold would make the eval **silently wrong**.

### `--limit` is not truncation, and that matters

Taking the first N documents would quietly break the eval. Gold documents can sit
anywhere in the corpus; any that got cut would make their `local` labels false — the
system genuinely does not have that answer. And in the eval that failure would look
like a **grader** error when the fault was the corpus. That is the worst kind of
measurement bug: it blames the wrong component.

So `load_corpus(limit=N)` keeps **all gold documents** first and fills the remaining
slots with filler. The filler is necessary — without it every indexed document would
answer some query and retrieval would be trivial. `test_corpus.py` asserts both
properties.

---

## backend/eval/build_scifact_scenarios.py

Generates eval cases from qrels. The `local` case labels come **from the dataset**: if
SciFact says claim Q is answered by abstract D, and D was ingested, then Q should route
local.

**The `web` cases are still hand-written, and that has to be acknowledged.** But they
are the easy half: SciFact is static scientific abstracts, so a question about today's
pricing cannot be in it. **The hard half — `local` — now comes from the dataset.**

---

## Corpus switching — the `CORPUS` env var

Either `concepts` (default) or `scifact`, in **separate Chroma collections**
(`crag_docs` / `crag_scifact`).

**Why separate collections rather than separate directories:** collections can coexist
in one `vectorstore/`, so switching needs **no re-ingest** — which on SciFact is minutes
of work. And there is no risk of mixing: SciFact chunks cannot surface in retrieval
alongside the 22 concepts chunks, which would make both sets of eval numbers worthless.

Results are per-corpus too (`results.json` / `results_scifact.json`), and `/api/stats`
reads whichever matches the active corpus. **Do not average them** — they measure
different things on different data.

### Two real bugs that only a larger corpus exposed

**OOM (exit 137), twice.** The whole corpus used to be split with every chunk held in
one list. On SciFact that is 17,266 chunks, and the 3.5 GB container died. On 22
concepts chunks this never shows. Fix: ingestion now **streams** — split, embed and
release a batch of documents at a time. Peak memory is now independent of corpus size.

**SQLite lock contention.** An ingest ran for five minutes and the vectorstore did not
grow by a byte. The cause: a running compose backend held the **same `vectorstore/`
mount**, and the ingest was blocked on Chroma's SQLite write lock. No error appears —
it simply hangs. Fix: stop compose before a large ingest.

---

## backend/app/tools/bm25_search.py

BM25 keyword search over the same chunks that are in Chroma.

**Why this alongside vector search:** they are strong at different things. Vector search
captures *meaning* — "annual time off" and "paid leave entitlement" land close together
without sharing a word. But it is weak on exact tokens: `EMP-4582` and `EMP-4583` sit
almost on top of each other in embedding space, because their *meaning* is the same.
BM25 is the inverse — exact term matching plus IDF — so it wins on identifiers, codes
and version numbers.

**Why it loads the whole corpus:** BM25's IDF depends on a term's **corpus-wide**
frequency. Running BM25 over only the top-k chunks would make IDF wrong and the scores
meaningless. On 22 chunks this is trivial — **the approach does not scale to a large
corpus**, where a proper inverted index (Elasticsearch, Tantivy) is required. That
limitation is real.

**Zero-score chunks are dropped:** in BM25, 0 means no query term appears in that chunk
at all. Ranking those only adds noise to the fusion.

**Stemming is deliberately absent:** another dependency (nltk, snowball) whose benefit
cannot be measured on 22 chunks — and this project runs on the rule that every addition
has to be measurable.

The index is built under `lru_cache`; `ingest.py` calls `bust_cache()` at the end, or a
stale index would persist in the same process after ingestion.

---

## backend/app/tools/reranker.py

Two things: cross-encoder reranking, and RRF fusion.

### Retriever vs reranker

- **Retriever = bi-encoder.** Embeds the query and document *separately*, which is what
  makes it fast: document vectors are precomputed. But it can never see the interaction
  between query and document, because the two never enter the model together.
- **Reranker = cross-encoder.** Query and document go into the model *together*. Far
  more accurate, but it costs one forward pass per pair — impossible across a corpus.

Hence two stages: the cheap retriever proposes 8 candidates, the expensive reranker
picks 4.

**In this project the reranker's purpose is not answer quality — it is the grader's
input.** If the right chunk was retrieved but left low in the top-k, the grader may not
see it properly and can return a wrong `no`.

### Why RRF does not normalise scores

Chroma returns a cosine **distance** (lower is better); BM25 returns an unbounded
positive score (higher is better). These are different scales, and converting between
them requires corpus-specific tuning, which is brittle.

RRF looks only at **rank**: `score(d) = Σ 1/(60 + rank)`. The scale of either list
becomes irrelevant — which is exactly why it is the default fusion for hybrid search.

**If the reranker fails it returns the original order** rather than raising. Reranking
is an *improvement*, not a requirement: if the model fails to load, retrieval should
keep working, just less accurately.

Model: `Xenova/ms-marco-MiniLM-L-6-v2`, an 80 MB ONNX model that ships with
`fastembed` — **no new dependency**, and the same local, no-key stance as the
embeddings.

---

## backend/app/tools/web_search.py — the provider abstraction

The `web_search_fallback` node searches through this layer and does not know what is
underneath. The provider is chosen by the `SEARCH_PROVIDER` env var, not in code.

**Why this layer exists:** DuckDuckGo works with no key (so the project runs on day
one), while Tavily gives better snippets but requires a signup. One interface makes
switching an env var, and lets a test replace the entire search layer in one line.

---

## backend/app/tools/duckduckgo_search.py — the default provider

Uses the `ddgs` package. **No API key, no signup.** The interface matches
`tavily_search` exactly — `(query, max_results) -> List[str]` — so nothing in the node
changes when the provider does.

The trade-off is explicit: DuckDuckGo's snippets are thinner and it throttles without
warning. But zero signup means the project runs immediately. With a key,
`SEARCH_PROVIDER=tavily`.

Both `ddgs` and the older `duckduckgo_search` import paths are handled — the package
was renamed, and an import should not break on version drift.

---

## backend/app/tools/tavily_search.py — the optional upgrade

A Tavily client wrapper: `tavily_search(query, max_results) -> List[str]`, returning
snippet text only. It gives the node a clean interface.

## backend/app/tools/vector_search.py

A Chroma similarity-search wrapper used by both the `retrieve` node and the ingestion
script — so k and any score threshold are tuned in one place.

---

## backend/main.py

The FastAPI entry point. The graph is compiled once in `lifespan` (rebuilding it per
request is wasted work). `POST /api/query` returns `answer`, `source_type`, `sources`,
`relevance_score`, `transformed_query`, `logs` and `elapsed_ms` — which is what the
badge and the trace viewer are built from.

**Why `run_in_threadpool`:** `graph.invoke` is synchronous and **blocks** on LLM and
search calls. Calling it directly inside an `async def` would let one slow request stall
the entire event loop, defeating the point of an async framework. Running it in a
threadpool keeps other requests moving.

**Why `/health` makes no LLM call:** a health check has to be cheap and reliable. If it
pinged the model, a single rate limit would mark the container unhealthy and Docker
would restart it in a loop. So it returns the index count and a config echo — including
`groq_key_set`, which is the first thing worth knowing when debugging a setup.

**CORS.** The default is now the two local dev origins (`CORS_ORIGINS`), not `*`. The
deploy image serves the built frontend from this same app, so production is same-origin
and this middleware never fires there — which is exactly why the permissive default was
worth removing rather than keeping "just in case". Set `CORS_ORIGINS` only for a split
deployment.

**Static mount.** When a `static/` directory exists — only in the single-service deploy
image — the built SPA is mounted at `/`. It is mounted **last**, because a mount at `/`
swallows every path beneath it and would make the API routes unreachable. The check is
on the directory rather than an env var, so there is one fewer thing to configure
correctly.

**Verified with real HTTP requests inside the container:** `/health` →
`{"status":"ok","indexed_chunks":22,...}`; an empty question → `422`; a query with no
Groq key → `500` with a clear "GROQ_API_KEY is not set" message.

---

## Dockerfiles

**`backend/Dockerfile`** — used by docker-compose. Python 3.11-slim; requirements copied
and installed first for layer caching; the FastEmbed embedding and reranker models
pulled at build time so the first request does not wait for a download; then `app/`,
`data/`, `eval/`, `ingest.py` and `main.py`.

**`Dockerfile` (repo root)** — the single-service deploy image. Builds the React app in a
node stage, then serves both the API and the bundle from one FastAPI process. It
**runs the ingest at build time** and asserts the index is non-empty, because
`backend/vectorstore/` is gitignored: a fresh clone — which is what a HuggingFace Space
builds from — would otherwise boot with an empty index. `backend/data/` is in git, so
the image can build the index itself, and it can never drift from the corpus it claims
to represent.

**`frontend/Dockerfile`** — multi-stage: build with node, then copy only `dist/` into an
Nginx image. There is no reason to ship a node runtime when only static files remain.

---

## frontend/ — React + Vite + Tailwind

A dashboard: a left nav rail, and one full-width view at a time (chat, documents,
evaluation, system).

There used to be a right rail and four stat cards across the top. Both were removed. The
rail repeated everything `Message` already showed (route, verdict, calls, time) and only
ever displayed the **last** answer — so asking two questions and pointing at "this one
graded no, this one yes" was impossible. The trace now sits inline under each answer.
The stat cards repeated on every view while each view writes its own numbers anyway.

| File | Role |
|---|---|
| `src/App.jsx` | Layout, conversation state, `fetch("/api/query")` and `/api/stats` |
| `components/Sidebar.jsx` | Nav rail, logo, recent-query list |
| `components/Message.jsx` | One turn — user bubble or assistant card (badge, rewrite note, citations) |
| `components/Citations.jsx` | Sources — filenames for local, clickable URLs for web |
| `views/{Chat,Documents,Evaluation,System}` | The full-page views the sidebar switches between |
| `components/TraceTimeline.jsx` | Renders `logs[]` as a node-by-node timeline, plus the `chain()` and `llmCalls()` helpers |
| `vite.config.js` | Proxies `/api` to the backend in dev |
| `nginx.conf` | The same `/api` proxy in production, plus SPA fallback |

**Why the app always uses a relative `/api/query`:** Vite proxies in dev, Nginx in
production, and the deploy image serves both from one origin. No backend URL is
hardcoded anywhere, so nothing has to be rebuilt for a deploy.

**Why the demo queries are fixed:** their expected route is known in advance. Typing
something arbitrary in a live demo and hoping the fallback triggers is how demos break.

**And why they change with the corpus:** the chips used to be hardcoded concepts
questions. Under `CORPUS=scifact`, the *"Why does chunk overlap matter"* chip would show
a green (local) dot while that document is not in the corpus at all — the web route
would actually run. The chip would be contradicting its own demo. The SciFact queries
come from `eval/results_scifact.json`: these are the cases that routed local in that run
**and** retrieved their gold document, so they will behave on a demo. The same applies
to the findings, the labelling note, and the Documents corpus note — all of them follow
`CORPUS`, or the UI ends up arguing with the numbers on its own screen.

**Every answer carries its own trace:** a one-line path under `Message` —
`retrieve / grade: no / rewrite / web search / generate / validate` — with the LLM call
count after it. On the local route it also reads `(fallback would cost 4)`, because "3
calls" alone says nothing; "3, and 4 on the fallback" is the trade-off conditional
routing rests on. Both numbers are counted from `logs[]`, not hardcoded. The chevron
opens the full timeline.

**The view lives in the URL hash:** `#eval`, `#documents`, `#system`. It used to be
`useState` alone — open Evaluation, refresh, and the app silently returned to Chat. A
hash rather than a path because a hash never reaches the server, so Nginx needs no
SPA-fallback rule. It uses `pushState` + `popstate` rather than `replaceState`: replace
fixes the refresh but creates no history entry, so the back button would not move
between views.

### What the UI deliberately does *not* show

These follow from one rule: **no number on screen without a real source behind it.**

**No "Relevance Score: 0.92".** The grader is **binary** — one word, `yes` or `no`.
Turning that into a two-decimal percentage is exactly the fake precision this project
rejects. The panel reads `Relevance Verdict: yes`. If asked "why 92 and not 85?", there
has to be an answer — and on a binary verdict the question cannot arise.

**No per-step timestamps in the trace.** The backend emits no per-node timing, so
printing `10:24:03` would be inventing a number. The total `elapsed_ms` is real, and
that is what is shown.

**"Web Search (skipped)" is shown on purpose.** On the local route that node never ran —
showing it greyed out is what makes clear that the fallback is **conditional, not the
default**. It puts the project's thesis on screen at a glance.

**The eval numbers carry their caveat.** Directly under 20/20, the Evaluation tab states
that "100% means the labelled task is easy, not that the router is perfect" — the same
thing `RESULTS.md` says. A dashboard should not leave an impression the docs contradict.

---

## docker-compose.yml

| Service | Role |
|---|---|
| `backend` | FastAPI + LangGraph, `vectorstore/` mounted as a volume, `/health` healthcheck |
| `frontend` | The React build served by Nginx, proxying `/api/` to the backend |

Chroma is embedded, not a separate service — persistence is just a mounted volume.

**A real bug found here:** `depends_on` used `condition: service_started`, which let
Nginx come up **before** uvicorn had bound, so the first query right after
`docker compose up` returned a **502 Bad Gateway**. Fixed with
`condition: service_healthy`. `/health` makes no LLM call, which is what makes that
check cheap and reliable.

**Why ports 3001/8001 rather than 3000/8000:** other projects on this machine hold those.
Both are overridable with `FRONTEND_PORT` / `BACKEND_PORT` in `.env`.

---

## .env.example

Real secrets live in `.env`, which is gitignored. `.env.example` is a template only —
it names the variables needed (`GROQ_API_KEY`, `TAVILY_API_KEY`, `CORS_ORIGINS`,
`VECTOR_DB`) without leaking a value.

**This file is committed, and that has consequences.** A real Groq key once reached it
and was pushed to a public repository. It was revoked, purged from the history, and the
remote force-pushed. Placeholders only, always.
