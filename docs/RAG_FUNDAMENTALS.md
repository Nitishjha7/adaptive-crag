# RAG Fundamentals — concepts and interview prep

General RAG knowledge: concepts, production architecture, and the questions that get
asked. The project-specific pitch and Q&A live in
[INTERVIEW_NOTES.md](INTERVIEW_NOTES.md); the line-by-line defence is in
[CODE_QA.md](CODE_QA.md).

---

> ## ⚠️ Read this first
>
> The "production-grade RAG" architecture below is **not this project's architecture**.
> Some of its stages exist here and some do not.
>
> Presenting that diagram as your own while an interviewer has the repository open is
> the single biggest credibility risk in this document.
> [Section 3](#3-this-project-vs-the-production-architecture) has the exact mapping —
> what is built, what is not.
>
> **The right framing:** *"Production RAG has a context-filtering stage and real
> document parsing. I didn't build those — I deliberately focused on the corrective
> loop and on measuring it."* That is honest and it shows scope awareness.

---

## Table of contents

1. [What RAG is, and why](#1-what-rag-is-and-why)
2. [The production RAG pipeline, stage by stage](#2-the-production-rag-pipeline-stage-by-stage)
3. [This project vs the production architecture](#3-this-project-vs-the-production-architecture)
4. [RAG → CRAG → Agentic RAG](#4-rag--crag--agentic-rag)
5. [Interview questions — basic](#5-interview-questions--basic)
6. [Interview questions — intermediate](#6-interview-questions--intermediate)
7. [Interview questions — advanced](#7-interview-questions--advanced)
8. [Scenario questions (the ones that matter)](#8-scenario-questions-the-ones-that-matter)

---

## 1. What RAG is, and why

**RAG = Retrieval-Augmented Generation.**

A plain LLM answers from its training knowledge. RAG looks up your data **at query
time** and hands it to the model, which answers from what it was given.

```
User question -> Retriever -> Relevant chunks -> LLM -> Answer
```

**Why it is needed:**

| Problem | How RAG addresses it |
|---|---|
| The model has never seen your company's data | Retrieve it at query time and put it in context |
| Knowledge goes stale | Update the index; no retraining |
| Hallucination | Ground the answer in retrieved evidence |
| "Where did this come from?" | Citations — source document and page |

**RAG vs fine-tuning** (asked almost every time):

```
Knowledge that keeps changing       -> RAG
Behaviour / style / format          -> Fine-tuning
Both                                -> Both
```

Fine-tuning teaches a model how to *behave*; RAG gives it *facts*. In a company policy
chatbot the policy can change tomorrow — fine-tuning that is the wrong tool.

---

## 2. The production RAG pipeline, stage by stage

There are two separate pipelines, and the distinction is worth making explicitly in an
interview:

```
INGESTION (offline — when a document is uploaded or updated)
┌──────────────┐
│  Documents   │
└──────┬───────┘
       v
 Document parser        extract clean text from PDF/DOCX
       v
   Chunking             split large documents into pieces
       v
  Embeddings            turn each chunk into a vector
       v
 Vector database        store vectors + text + metadata


QUERY TIME (online — on every user question)
User query
    v
 Query rewrite          make the question retrieval-friendly
    v
 Hybrid retrieval
    /        \
Vector      BM25        meaning-based + keyword-based
    \        /
   Reranker             rescore the top-K with a better model
       v
 Context filter         pass only the genuinely useful chunks
       v
  LLM / agent
       v
 Grounded answer        based on the retrieved evidence
       v
   Citations            source file + page
```

### 2.1 Document parser

A PDF is not just text — tables, images, headers, footers, multi-column layouts. The
parser has to get usable text out of all of it.

**Why it matters:** if the parser reads a two-column PDF wrongly, everything downstream
runs on garbage. "The document definitely contains it but RAG can't answer" most often
traces back to here — and most people blame the embedding model instead.

### 2.2 Chunking

One embedding for a whole 100-page document is useless — that vector represents the
document's *average* topic and matches no specific question.

```
100-page doc -> chunk 1, chunk 2, ... chunk 500
```

**The chunk-size trade-off:**

| Size | Problem |
|---|---|
| Too small (~100 chars) | Context is lost — you get "18 days" with no idea what for |
| Too large (~5000 chars) | The relevant line is averaged away with unrelated text (dilution) |

A common starting point is **800 characters with 100 of overlap**, which is what this
project uses (`backend/app/config.py`).

**Why overlap:** if a sentence is split across two chunks, neither retrieves well.
Overlap keeps that boundary sentence whole in at least one chunk. Typically 10–15% of
the chunk size.

**Recursive character splitting:** tries a list of separators in order — paragraph
break, then line break, then sentence, then word. It keeps semantically related text
together far more often than cutting at a fixed character count.

### 2.3 Embeddings

Text → a fixed-length float vector representing **meaning**.

```
"Employees get 18 paid leaves"  ->  [0.12, -0.42, 0.87, ...]
```

Which is why these two land close together despite sharing almost no words:

- "How many paid leaves do employees get?"
- "What is the annual leave entitlement?"

**Cosine similarity** measures the *angle* between two vectors and ignores magnitude.
Ignoring magnitude matters because embedding length often varies with text length
rather than with meaning.

**The model-size trade-off:** small models (`bge-small`, 384 dims) run fast on CPU;
larger ones (768/1024 dims) capture finer distinctions at more cost. On a small corpus,
**good chunking makes more difference than a better embedding model.**

### 2.4 Vector database

Stores embeddings plus the original text and metadata, and answers nearest-neighbour
queries.

**Exact vs approximate (ANN):** exact search compares against every vector — perfectly
accurate, and fine up to roughly a hundred thousand vectors. Beyond that, ANN indexes
like HNSW trade a little recall for a large speed gain.

**Embedded vs server mode:** Chroma in embedded mode runs as a library writing to a
directory, with no separate process — enough for a demo or a small internal tool.
Server mode is what you want once multiple application instances share an index.

**Metadata filtering:** filter alongside the similarity search — to one document, a date
range, an access level. Filtering **first** is better than trimming results afterwards,
because it keeps irrelevant material out of the candidate set entirely.

### 2.5 Query rewrite

Users write conversationally; retrieval wants something else.

```
"hey how much paid time off do I actually get?"
        v
"annual paid leave entitlement employees"
```

**HyDE (Hypothetical Document Embeddings)** inverts the idea: generate a *hypothetical
answer* first, then embed that and use it as the query. Because the hypothetical answer
is written in the corpus's declarative register, its embedding often sits closer to the
real answer than the question's does. It does not need to be factually correct — only
structurally similar.

**Multi-query expansion:** generate three or four paraphrases, retrieve for each, merge.
Recall goes up, cost goes up.

**Decomposition:** a compound question ("compare X's v2 pricing with v1") retrieves
badly as one query, because no single chunk covers both halves. Split it into
sub-questions.

### 2.6 Hybrid retrieval: vector + BM25

| | Strong at |
|---|---|
| **Vector search** (dense) | Meaning. "time off" ≈ "leave entitlement" |
| **BM25** (sparse, keyword) | Exact tokens — `EMP-4582`, `SKU-12345`, `18`, product names |

Vector search is surprisingly poor on exact identifiers, because `EMP-4582` and
`EMP-4583` mean almost the same thing in embedding space. BM25 matches them exactly.

So production systems run both and fuse the scores, usually with Reciprocal Rank
Fusion.

### 2.7 Reranker

Retrieval returns 20 chunks; the reranker **rescores** them with a heavier
cross-encoder that reads the query and chunk *together*.

**The real difference between a retriever and a reranker:**

- The retriever embeds query and document **separately** (bi-encoder). That is what
  makes it fast — document vectors are precomputed — but it never sees their
  interaction.
- The reranker puts query and document into the model **together** (cross-encoder).
  Much more accurate, but one forward pass per pair, so it only runs on the top 20, not
  the corpus.

Hence two steps: a cheap retriever fetches 20, an expensive reranker picks 5.

### 2.8 Context filter → LLM → grounding → citations

- **Context filter** — drop chunks below a relevance threshold. Stuffing the model hurts
  ("lost in the middle": models do not reliably read material buried in a long context).
- **Grounded answer** — based on the retrieved evidence, not the model's own memory.
- **Citations** — source file and page, so the user can verify.

---

## 3. This project vs the production architecture

**Learn this table before an interview.** It is what tells you what to claim and what
not to.

| Stage | Production RAG | In Adaptive CRAG? |
|---|---|---|
| Document parser | PDF/DOCX/HTML extraction | 🟡 Only `.md`/`.txt` — the corpus is already plain text |
| Chunking | Recursive, structure-aware | ✅ `RecursiveCharacterTextSplitter`, 800/100, `\n## ` first |
| Embeddings | Hosted or local | ✅ FastEmbed `bge-small-en-v1.5`, local ONNX |
| Vector DB | Pinecone / Weaviate / Qdrant | ✅ Chroma, embedded mode |
| **Query rewrite** | **Before** retrieval | 🟡 Present, but **after** — only on the fallback path. See below |
| **Hybrid retrieval** | Vector + BM25 | ✅ Both, fused with RRF (`USE_HYBRID`) |
| **Reranker** | Cross-encoder | ✅ `ms-marco-MiniLM-L-6`, local ONNX (`USE_RERANKER`) |
| Context filter | Threshold / compression | ❌ Not built. The top-4 after reranking go straight to `generate` |
| **Retrieval evaluator** | Usually absent | ✅ **Present — this is the project's core** |
| **Web fallback** | Usually absent | ✅ **Present — conditional, not always-on** |
| Grounding check | Sometimes | ✅ An independent LLM check plus PII redaction |
| Citations | File + page number | 🟡 `[source: URL]` on web results; none on local chunks |
| Evaluation | RAGAS / custom | ✅ Two corpora, labelled sets, published negative results |

### The placement of query rewrite — this can get caught

In the production diagram, rewriting happens **before** retrieval, to make retrieval
itself better.

Here, `transform_query` runs **after grading**, and only when the local context was
graded `no`:

```
retrieve -> grade -> "no" -> transform_query -> web search
```

**Why:** the rewrite's job here is not to improve vector retrieval — that already
happened and was rejected. Its job is to turn a conversational question into keywords
for a **web search engine**. Two different purposes.

If asked *"why not rewrite first?"* the correct answer is: *"pre-retrieval rewriting is
a separate optimisation, and its benefit would have to be measured. I didn't build
it."* Do not claim your placement is better than the production one.

### What to say about what is missing

Two real gaps remain:

**"Why no context filter?"**
> "After reranking, the top 4 go straight to generation — there is no relevance
> threshold dropping a weak chunk. The reranker's scores are right there, so it is a
> small fix; I didn't do it because on 22 chunks the benefit cannot be measured."

**"Why no PDF/DOCX parsing?"**
> "The corpus is Markdown, so no parser was needed. It is a genuine gap — a large share
> of production retrieval bugs start there, because two-column PDFs and tables extract
> badly and the whole pipeline then runs on garbage."

**On hybrid and reranking** — they *are* built, and the thing worth saying is that the
**sequencing** is the point:

> "I built hybrid retrieval and the reranker deliberately **last**. At that stage
> routing accuracy was pinned at 100% and could not move — meaning any retrieval
> improvement I added would have been unprovable. So first I added ambiguous cases to
> the eval that a number *could* move on, then built the features, then ran the same set
> in both configurations and compared."

And then the honest part: **the comparison came back negative.** 27 of 28 cases
retrieved different chunks and not one routing decision changed. That is in
[RESULTS.md](../backend/eval/RESULTS.md), with the explanation — the grader
concatenates its chunks, so ordering is invisible to it.

---

## 4. RAG → CRAG → Agentic RAG

```
Naive RAG          retrieve -> stuff -> generate. Blind trust in retrieval
     v
Advanced RAG       + rewrite, hybrid, rerank, compression. Better retrieval,
                   still no verification
     v
CRAG               + a retrieval evaluator. "Is what came back usable?" If not, correct
     v
Self-RAG           the model critiques both its retrieval AND its generation
     v
Agentic RAG        an agent decides what to retrieve, from which source,
                   and what to do next
```

**Where this project sits:** CRAG, with some of the Advanced-RAG layer. The evaluator,
the correction path (web fallback) and output validation are the core. Hybrid retrieval
and reranking exist too — added last, behind flags, specifically so their effect could
be measured rather than assumed.

The naive-RAG failure modes CRAG addresses:

1. **Retrieval mismatch** — similarity search always returns k results, whether or not
   anything relevant exists. A low score never reaches the model.
2. **Staleness** — a fact changed; the system answers confidently from the old version.
3. **Lost in the middle** — models do not reliably read material buried mid-context.
4. **No abstention** — a naive pipeline has no path ending in "I don't know", because
   generation is unconditional.

---

## 5. Interview questions — basic

> ✅ = answerable directly from this project, which is always the strongest kind

| # | Question | Anchor |
|---|---|---|
| 1 | What is RAG and why is it needed? | ✅ Section 1 |
| 2 | RAG vs fine-tuning? | ✅ Changing knowledge → RAG |
| 3 | The end-to-end RAG workflow? | ✅ Describe ingestion and query time separately |
| 4 | What is an embedding? | ✅ `bge-small`, 384 dims |
| 5 | What is a vector DB and what is its role? | ✅ Chroma, embedded |
| 6 | Why chunk at all? | ✅ 800/100; one vector for a whole document is useless |
| 7 | How would you choose a chunk size? | ✅ The trade-off table in 2.2 |
| 8 | What is overlap and why? | ✅ Boundary sentences, 10–15% |
| 9 | Semantic vs keyword search? | ✅ Both are built — vector + BM25, fused with RRF |
| 10 | Why cosine and not Euclidean? | ✅ Magnitude varies with text length |
| 11 | What is the role of the context window? | ✅ Lost in the middle |

## 6. Interview questions — intermediate

| # | Question | Anchor |
|---|---|---|
| 12 | Limitations of naive RAG? | ✅ **The whole project answers this** — four failure modes |
| 13 | What are hybrid search and BM25? | ✅ Built. `bm25_search.py`, RRF fusion, and the honest A/B result |
| 14 | Dense vs sparse retrieval? | ✅ Section 2.6, and both are in the code |
| 15 | What is a reranker, how does it differ from a retriever? | ✅ Built. Bi-encoder vs cross-encoder — know this cold |
| 16 | How would you choose Top-K? | ✅ k=4. More k is not monotonically better — lost in the middle |
| 17 | The relevant doc isn't in the Top-K. Now what? | Rewrite, multi-query, raise k, hybrid, rerank |
| 18 | How would you debug poor retrieval? | ✅ See section 8 |
| 19 | Metadata filtering? | 🟡 Chroma supports it; this project does not use it |
| 20 | Query rewriting? | ✅ Present — but on the fallback path. See section 3 |
| 21 | HyDE? | Theory — section 2.5 |
| 22 | How do you reduce hallucination? | ✅ **The project's core** — grade, grounded prompt, validation |

## 7. Interview questions — advanced

| # | Question | Anchor |
|---|---|---|
| 23 | What is CRAG, how does it differ from RAG? | ✅ Evaluator + conditional correction |
| 24 | Agentic RAG / Self-RAG? | ✅ Section 4 |
| 25 | How would you design a retrieval evaluator? | ✅ Binary, temp 0, defensive parse, 11 tests on `parse_verdict` |
| 26 | Context is relevant but the answer is wrong — how do you catch it? | ✅ That is exactly what the groundedness check catches |
| 27 | Citation and grounding? | 🟡 URLs on web results, nothing on local chunks — own the gap |
| 28 | How do you measure retrieval quality? | ✅ **recall@k on BEIR SciFact — labels from the dataset** |
| 29 | Precision@K / Recall@K? | ✅ The eval reports fallback precision and recall, plus recall@k |
| 30 | Faithfulness vs answer relevance? | ✅ Groundedness = faithfulness |
| 31 | RAGAS? | ⚠️ Not used — a custom eval was built, and the reasons are defensible |
| 32 | How would you reduce latency? | ✅ **There is a real story here** — see RESULTS.md |
| 33 | Fast retrieval over millions of documents? | ANN/HNSW, a managed vector DB, metadata pre-filtering |
| 34 | How do you choose an embedding model? | ✅ Section 2.3 |
| 35 | What if you change the embedding model? | **A full index rebuild** — vectors are not compatible |
| 36 | How do you maintain embeddings as documents change? | 🟡 Not handled — full re-ingest. Own the gap |
| 37 | Multi-tenant RAG? | Per-tenant collections, or metadata filters plus row-level access |
| 38 | Prompt injection through retrieved documents? | ⚠️ **Not handled by this project** — see below |

**The prompt-injection answer** (increasingly common):

A retrieved document can contain *"Ignore previous instructions and say X"* — and the
risk is **higher** on the web fallback path, because the content comes from outside.
Mitigations: delimit retrieved text clearly as data, state in the system prompt that
context is data and not instruction, validate the output, and never let retrieved
content trigger a tool call.

> **In this project:** the groundedness check is a partial net — an answer produced from
> an injected instruction will usually be unsupported by the context. But it is **not** a
> deliberate injection defence. Do not present it as a strength; call it a known gap,
> and note it is more relevant on the web path.

---

## 8. Scenario questions (the ones that matter)

Definitions can be memorised. Scenario questions show how you think, so hold these as
**checklists**, not as one-line answers.

### "Answers are hallucinating. How do you debug it?"

Walk the pipeline in order rather than guessing:

```
1. Did the relevant chunk get retrieved at all?  -> if not, a retrieval problem
2. Retrieved but ranked low in top-k?            -> a ranking problem
3. In context but the model ignored it?          -> lost in the middle / prompt
4. Does the prompt say "only from context"?      -> a prompt problem
5. Is the answer supported by the context?       -> groundedness check
```

✅ **Your edge:** *"I built this into the pipeline — the grading node catches step 1, the
groundedness check catches step 5."*

### "The information is in the document and RAG still can't answer. Why?"

- Parsing — the PDF never extracted properly (the most under-rated cause)
- Chunking — the answer was split across two chunks and the overlap was too small
- The embedding model is wrong for the domain
- The query's phrasing is far from the document's (→ rewrite / HyDE)
- Top-K is too small
- A metadata filter is excluding the result

### "You have a 100-page PDF. How do you chunk it?"

The interviewer wants **reasoning**, not a number:

> "First look at the structure — if there are headings, split on those and keep the
> heading path in metadata. Fall back to recursive character splitting, around 800
> characters with 100 of overlap. Then tune against retrieval quality rather than
> guessing. Tables need separate handling, because naive splitting breaks them."

### "Vector search isn't returning relevant results. What do you change?"

Cheapest to most expensive, in this order:

```
Chunking -> Query rewrite -> Top-K -> Metadata filter
         -> Hybrid (BM25) -> Reranker -> Change the embedding model
```

Changing the embedding model is last because it forces a **full index rebuild**.

### "A company knowledge chatbot — RAG or fine-tuning?"

> "RAG. The knowledge keeps changing, and fine-tuning would mean retraining on every
> policy update. Fine-tune when you need to fix tone or format — but the facts should
> come from RAG."

### "Design a production-grade RAG system"

Draw the section 2 diagram, then add these — this is what shows seniority:

- **Evaluation** — a labelled set, run in CI, catching regressions
- **Observability** — a trace per query: what was retrieved, which route was taken
- **Caching** — embedding and generation caches for repeated queries
- **Access control** — metadata filters in a multi-tenant setup
- **Prompt-injection protection**
- **A re-index pipeline** — documents change

✅ **Your edge:** you **actually have** the evaluation and the observability — the eval
harness and the trace viewer. Most candidates only describe them.

---

## One last thing

The strongest answers are the ones **anchored in your own code**. "Chunk overlap
matters" is theory. *"I used 800/100 and put `\n## ` first in the separator list so
splits land on heading boundaries — it's in `backend/ingest.py`"* is experience.

So prepare the ✅ rows first. And treat the ❌ rows — the context filter, document
parsing, citations on local chunks — as **gaps to own**, not to hide. "I didn't build
that, and here's why" always beats "yes, that's in there too", because the second one
comes apart on the first follow-up question.
