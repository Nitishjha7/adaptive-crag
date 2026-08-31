# Demo Corpus — controlled, with a deliberate gap

Ye 7 docs local knowledge base hai. Content deliberately RAG/agent engineering
**concepts** tak seemit hai — aur usme ek jaan-boojh ke chhoda hua gap hai, taaki
demo me web fallback **predictably** trigger ho (live randomness pe depend na karna pade).

## Kya cover hai (→ `grade: yes`, source = Local Vector DB)

| Doc | Topic |
|---|---|
| `01_vector_embeddings.md` | embeddings, cosine similarity, local vs hosted |
| `02_chunking_strategies.md` | chunk size, overlap, recursive splitting |
| `03_vector_databases.md` | exact vs ANN, embedded vs server, persistence |
| `04_naive_rag_failure_modes.md` | retrieval mismatch, staleness, lost-in-the-middle |
| `05_corrective_rag.md` | CRAG evaluator, fallback rationale |
| `06_query_transformation.md` | rewriting, HyDE, decomposition |
| `07_agent_graphs_and_state.md` | nodes, conditional edges, reducers |

## Kya deliberately **nahi** hai (→ `grade: no`, source = Web Fallback)

- Koi bhi **specific product / vendor / pricing** detail (Tavily plans, Groq limits, model pricing)
- Koi bhi **recent news / release** (naye model launches, version numbers)
- **Model Context Protocol (MCP)** — ek pura relevant-sounding topic, corpus me zero mention

Ye gap isliye chuna gaya ki fallback query **web se genuinely answerable** ho. Agar corpus
kisi fictional company ka hota, to `grade: no` to aata, lekin web search bhi kachra deta —
demo ka doosra half mar jaata.

## Fixed demo queries

| # | Query | Expected route |
|---|---|---|
| 1 | Why is cosine similarity used for text embeddings instead of Euclidean distance? | `local` |
| 2 | Why does chunk overlap matter when splitting documents? | `local` |
| 3 | Why does CRAG replace the local documents on fallback instead of merging them? | `local` |
| 4 | What is the Model Context Protocol and what problem does it solve? | `web` |
| 5 | What is the current pricing of the Tavily search API? | `web` |

Phase 8 (eval script) inhi ko `eval/scenarios.json` me expected-route labels ke saath
use karega.
