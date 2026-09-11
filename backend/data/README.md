# Demo corpus — controlled, with a deliberate gap

These 7 documents are the local knowledge base. The content is deliberately
limited to RAG and agent engineering **concepts**, and it has a hole cut in it on
purpose, so the web fallback fires **predictably** in a demo rather than
depending on live randomness.

## What is covered (→ `grade: yes`, source = local vector DB)

| Doc | Topic |
|---|---|
| `01_vector_embeddings.md` | embeddings, cosine similarity, local vs hosted |
| `02_chunking_strategies.md` | chunk size, overlap, recursive splitting |
| `03_vector_databases.md` | exact vs ANN, embedded vs server, persistence |
| `04_naive_rag_failure_modes.md` | retrieval mismatch, staleness, lost-in-the-middle |
| `05_corrective_rag.md` | CRAG evaluator, fallback rationale |
| `06_query_transformation.md` | rewriting, HyDE, decomposition |
| `07_agent_graphs_and_state.md` | nodes, conditional edges, reducers |

## What is deliberately **absent** (→ `grade: no`, source = web fallback)

- Any **specific product, vendor or pricing** detail (Tavily plans, Groq limits,
  model pricing)
- Any **recent news or release** (new model launches, version numbers)
- **Model Context Protocol (MCP)** — an entire relevant-sounding topic with zero
  mentions in the corpus

The gap was chosen so that the fallback query is **genuinely answerable from the
web**. If the corpus were about a fictional company, `grade: no` would still
fire, but the web search would return noise too — and the second half of the demo
would die with it.

## Fixed demo queries

| # | Query | Expected route |
|---|---|---|
| 1 | Why is cosine similarity used for text embeddings instead of Euclidean distance? | `local` |
| 2 | Why does chunk overlap matter when splitting documents? | `local` |
| 3 | Why does CRAG replace the local documents on fallback instead of merging them? | `local` |
| 4 | What is the Model Context Protocol and what problem does it solve? | `web` |
| 5 | What is the current pricing of the Tavily search API? | `web` |

`eval/scenarios.json` uses these with expected-route labels.
