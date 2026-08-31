# Adaptive CRAG: Technical Specification & Implementation Guide

Adaptive Corrective Retrieval-Augmented Generation with web-search fallback.

**Core framework:** LangGraph (StateGraph) · LangChain · FastAPI (Python 3.11, ASGI) · React + Vite
**Target domain:** Agentic RAG, retrieval verification, hallucination mitigation
**Pattern references:** LangGraph CRAG cookbook, Self-RAG, Corrective RAG (Yan et al. 2024)

---

## 1. Executive Summary & Core Value Proposition

Standard RAG architectures assume retrieved vector chunks are always relevant, which leads
to hallucinations or ungrounded responses when the local data is out-of-domain, ambiguous,
or stale. Adaptive CRAG overcomes this through **active evaluation**:

- **Self-grading context** — a dedicated node assesses whether retrieved local documents
  sufficiently answer the query, before any answer is generated.
- **Autonomous query transformation** — if local documents are insufficient, the agent
  refactors the query into optimized keyword searches for a search engine.
- **Live web fallback** — a real-time web search API fetches up-to-date external context
  only when it's actually needed.
- **Hallucination & policy guardrails** — an output-validation layer prevents context
  leakage and enforces grounded, factual responses.

The key design decision: **web search is a fallback, not a default.** A local hit is fast
and cheap; the fallback fires only when grading says the local context can't answer the
question.

---

## 2. System Architecture

```
[ React + Vite + Tailwind Frontend ]
  |-- Chat UI
  |-- Source badge (Local Vector DB / Live Web Fallback)
  \-- LangGraph execution-trace viewer (which node ran, in what order)
                           |
                           v  (async ASGI)
[ FastAPI Backend ]
  |-- POST /api/query        run the CRAG graph, return answer + source + logs
  \-- GET  /health           container healthcheck
                           |
                           v
[ LangGraph StateGraph — CRAGState ]
  retrieve -> grade_documents -> [conditional]
                                   |-- relevant   --> generate --------+
                                   \-- irrelevant --> transform_query  |
                                                        -> web_search_fallback
                                                        -> generate ---+
                                                                       v
                                                          validate_guardrails
                                                                       v
                                                               final_output
                           |
       +-------------------+-------------------+
       v                                       v
[ ChromaDB ]                           [ DuckDuckGo / Tavily ]
  local document embeddings              live web search snippets
  (cosine similarity, top-k)             (only on fallback)
                           |
                           v
[ Output validation ]  LLM groundedness check + regex PII redaction
```

### Component matrix

| Component | Technology | Primary role |
|---|---|---|
| Agent orchestration | LangGraph StateGraph | Conditional branching, corrective loop, state threading |
| Grading / synthesis LLM | Groq (`openai/gpt-oss-120b`) via LangChain | Binary relevance grading, query rewrite, answer generation |
| Embeddings | FastEmbed / HuggingFace | Local document + query vectorization |
| Local knowledge base | ChromaDB / FAISS | Vector storage, cosine top-k similarity search |
| Web search tool | DuckDuckGo (default, no key) / Tavily (optional) | Fallback context when local docs graded irrelevant |
| Output validation | Custom LLM groundedness check + regex PII | Catches ungrounded claims and redacts PII from the final answer |
| Backend | FastAPI + Uvicorn | REST endpoint, retrieval scores, step execution logs |
| Frontend | React + Vite + Tailwind CSS | Chat, source badges, relevance indicators, trace |
| Containerization | Docker & Docker Compose | Backend + vector DB + frontend orchestration |

---

## 3. LangGraph CRAG State Machine & Routing Logic

The graph models an adaptive decision loop where context grading dictates the downstream
execution path.

```
                       +-------------------+
                       |    User Query     |
                       +-------------------+
                                 |
                                 v
                       +-------------------+
                       | Retrieve Context  |
                       | (Vector DB / RAG) |
                       +-------------------+
                                 |
                                 v
                       +-------------------+
                       | Grade Documents   |
                       +-------------------+
                                 |
                     [Conditional Evaluator]
                                 |
            +--------------------+--------------------+
            | (Relevant)                              | (Irrelevant / Low Score)
            v                                         v
+------------------------+                  +-------------------+
|     Generate Answer    |                  |   Rewrite Query   |
+------------------------+                  +-------------------+
            |                                         |
            |                                         v
            |                               +-------------------+
            |                               |  Web Search Tool  |
            |                               |  (Tavily Search)  |
            |                               +-------------------+
            |                                         |
            |                                         v
            |                               +-------------------+
            |                               | Generate (Web Ctx)|
            |                               +-------------------+
            |                                         |
            +--------------------+--------------------+
                                 |
                                 v
                       +--------------------+
                       | Guardrail Validate |
                       +--------------------+
                                 |
                                 v
                       +--------------------+
                       |    Final Output    |
                       +--------------------+
```

### CRAGState schema definition

```python
from typing import List
from typing_extensions import TypedDict

class CRAGState(TypedDict):
    question: str            # Original user query
    transformed_query: str   # Web-optimized search query (set by transform_query)
    documents: List[str]     # Retrieved chunks — local first, replaced by web on fallback
    relevance_score: str     # Graded status: "yes" (relevant) or "no" (irrelevant)
    source_type: str         # "vector_db" or "web_search"
    generation: str          # Raw synthesized answer
    final_output: str        # Guardrail-validated final response
    logs: List[str]          # Node trace execution logs
```

`documents` and `logs` use additive reducers so each node appends without clobbering.

---

## 4. Node Breakdown & Core Execution Logic

| Graph node | Primary operation | Output / transition |
|---|---|---|
| `retrieve` | Vector similarity search against ChromaDB using cosine distance | Appends top-k document chunks to `documents`; `source_type = "vector_db"` |
| `grade_documents` | LLM binary grader scores retrieved context relevance against the query | Sets `relevance_score` to `"yes"` or `"no"` |
| `transform_query` | Rewrites natural-language question into search-engine optimized keywords | Updates `transformed_query` |
| `web_search_fallback` | Queries Tavily / DuckDuckGo with `transformed_query` | Replaces `documents` with web snippets; `source_type = "web_search"` |
| `generate` | Synthesizes a natural-language answer grounded exclusively in verified context | Produces draft answer in `generation` |
| `validate_guardrails` | Scans output for hallucination, PII leakage, toxic content | Returns validated `final_output` and full execution trace |

### Conditional edge

```python
def decide_to_generate(state: CRAGState) -> str:
    return "generate" if state["relevance_score"] == "yes" else "transform_query"

graph.add_conditional_edges(
    "grade_documents",
    decide_to_generate,
    {"generate": "generate", "transform_query": "transform_query"},
)
```

---

## 5. Reference Implementation Snippets

### A. Graph construction — `backend/app/graph/build_graph.py`

```python
from langgraph.graph import StateGraph, START, END
from app.schemas.crag_state import CRAGState
from app.nodes import (
    retrieve, grade_documents, transform_query,
    web_search_fallback, generate, validate_guardrails,
)

def build_crag_graph():
    g = StateGraph(CRAGState)
    g.add_node("retrieve", retrieve.run)
    g.add_node("grade_documents", grade_documents.run)
    g.add_node("transform_query", transform_query.run)
    g.add_node("web_search_fallback", web_search_fallback.run)
    g.add_node("generate", generate.run)
    g.add_node("validate_guardrails", validate_guardrails.run)

    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "grade_documents")
    g.add_conditional_edges(
        "grade_documents",
        lambda s: "generate" if s["relevance_score"] == "yes" else "transform_query",
        {"generate": "generate", "transform_query": "transform_query"},
    )
    g.add_edge("transform_query", "web_search_fallback")
    g.add_edge("web_search_fallback", "generate")
    g.add_edge("generate", "validate_guardrails")
    g.add_edge("validate_guardrails", END)
    return g.compile()
```

### B. Binary relevance grader — `backend/app/nodes/grade_documents.py`

```python
from langchain_core.prompts import ChatPromptTemplate
from app.config import get_llm

GRADER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a grader assessing whether retrieved documents are relevant to a user "
     "question. Answer with a single word: 'yes' if the documents contain information "
     "that helps answer the question, otherwise 'no'. Do not explain."),
    ("human", "Question: {question}\n\nRetrieved documents:\n{documents}"),
])

def run(state: dict) -> dict:
    llm = get_llm()
    chain = GRADER_PROMPT | llm
    verdict = chain.invoke({
        "question": state["question"],
        "documents": "\n---\n".join(state["documents"]),
    }).content.strip().lower()
    score = "yes" if "yes" in verdict else "no"
    return {
        "relevance_score": score,
        "logs": [f"grade_documents -> {score}"],
    }
```

### C. Query transform — `backend/app/nodes/transform_query.py`

```python
from langchain_core.prompts import ChatPromptTemplate
from app.config import get_llm

REWRITE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Rewrite the user question into a concise, keyword-focused web search query. "
     "Return only the rewritten query, no quotes, no preamble."),
    ("human", "{question}"),
])

def run(state: dict) -> dict:
    rewritten = (REWRITE_PROMPT | get_llm()).invoke(
        {"question": state["question"]}
    ).content.strip()
    return {
        "transformed_query": rewritten,
        "logs": [f"transform_query -> {rewritten!r}"],
    }
```

### D. Web search fallback — `backend/app/nodes/web_search_fallback.py`

```python
from app.tools.web_search import web_search   # provider switch, not a specific vendor

def run(state: dict) -> dict:
    query = state.get("transformed_query") or state["question"]
    try:
        snippets = web_search(query, max_results=4)   # -> List[str]
    except Exception as exc:
        # Search failure is recoverable: `generate` handles empty documents and says
        # plainly that no context was found. Raising here would 500 the request.
        return {
            "documents": [],
            "source_type": "web_search",
            "logs": [f"web_search_fallback -> FAILED ({type(exc).__name__}: {exc})"],
        }
    return {
        "documents": snippets,          # replaces local docs, does not merge
        "source_type": "web_search",
        "logs": [f"web_search_fallback -> {len(snippets)} snippets for {query!r}"],
    }
```

### E. Output validation — `backend/app/nodes/validate_guardrails.py`

`validate_answer` runs a temperature-0 groundedness check ("is every claim supported by
this context?") and regex PII redaction. An ungrounded answer is **flagged, not blocked**;
PII **is** redacted. The groundedness check fails open — see [CODE_NOTES.md](CODE_NOTES.md).

```python
from app.guardrails.validators import validate_answer

def run(state: dict) -> dict:
    result = validate_answer(
        answer=state["generation"],
        context=state["documents"],
        question=state["question"],
    )
    return {
        "final_output": result.validated_output,
        "logs": [f"validate_guardrails -> pass={result.passed}"],
    }
```

### F. FastAPI endpoint — `backend/main.py`

```python
from fastapi import FastAPI
from pydantic import BaseModel
from app.graph.build_graph import build_crag_graph

app = FastAPI(title="Adaptive CRAG")
graph = build_crag_graph()

class QueryIn(BaseModel):
    question: str

@app.post("/api/query")
async def query(body: QueryIn):
    final = graph.invoke({
        "question": body.question,
        "documents": [],
        "source_type": "vector_db",
        "logs": [],
    })
    return {
        "answer": final["final_output"],
        "source_type": final["source_type"],
        "relevance_score": final["relevance_score"],
        "logs": final["logs"],
    }

@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

## 6. Implementation & Build Guide

1. **Vector store initialization** — ingest local documents into a ChromaDB collection
   using fast local embeddings (FastEmbed). Persist to a Docker volume.
2. **LangGraph workflow construction** — define nodes and attach conditional edges based
   on the document-grader output.
3. **FastAPI endpoint creation** — expose `POST /api/query` accepting user prompts and
   returning answers with source tags (Local DB vs Web) and step logs.
4. **React frontend dashboard** — chat UI with citation badges (`Local Vector DB` /
   `Live Web Fallback`) and a node-by-node execution trace panel.

---

## 7. Project File Structure

```
adaptive-crag/
├── backend/
│   ├── app/
│   │   ├── config.py                  # Settings + LLM / embedding / vectorstore factories
│   │   ├── graph/
│   │   │   ├── state.py               # re-export of CRAGState
│   │   │   └── build_graph.py         # StateGraph wiring + conditional edge
│   │   ├── nodes/
│   │   │   ├── retrieve.py
│   │   │   ├── grade_documents.py     # binary grader + defensive parse_verdict
│   │   │   ├── transform_query.py
│   │   │   ├── web_search_fallback.py
│   │   │   ├── generate.py
│   │   │   └── validate_guardrails.py
│   │   ├── tools/
│   │   │   ├── vector_search.py
│   │   │   ├── web_search.py          # provider switch (SEARCH_PROVIDER)
│   │   │   ├── duckduckgo_search.py   # default — no API key
│   │   │   └── tavily_search.py       # optional upgrade
│   │   ├── schemas/crag_state.py      # CRAGState (canonical definition)
│   │   ├── guardrails/validators.py   # groundedness + PII
│   │   └── __main__.py                # `python -m app "question"` CLI
│   ├── data/                          # 7-doc controlled corpus with a deliberate gap
│   ├── tests/                         # 27 tests — routing, grading, validation, API
│   ├── vectorstore/                   # persisted Chroma index (gitignored)
│   ├── ingest.py                      # docs -> chunks -> embeddings -> Chroma
│   ├── main.py                        # FastAPI app
│   └── Dockerfile · requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/{ChatBox,SourceBadge,TraceViewer,RelevancePill}.jsx
│   │   └── App.jsx · main.jsx · index.css
│   ├── package.json · tailwind.config.js · vite.config.js · postcss.config.js
│   ├── nginx.conf                     # SPA fallback + /api/ proxy to backend
│   └── Dockerfile                     # multi-stage: node build -> nginx serve
├── docs/
├── dev.ps1                            # backend-only Docker dev loop
└── docker-compose.yml · .gitignore · .env.example · README.md
```

> Two differences from the original plan: there is no `pages/Home.jsx` (the app is small
> enough that `App.jsx` composes it directly), and `guardrails/validators.py` is a custom
> implementation rather than Guardrails AI — see [CODE_NOTES.md](CODE_NOTES.md) for why.

---

## 8. Containerization & Deployment Model

Multi-service Docker Compose:

- **backend** — `python:3.11-slim`, FastAPI + Uvicorn, LangGraph, Chroma
  persistence volume mounted at `backend/vectorstore`.
- **frontend** — multi-stage Node build served by Nginx with an `/api/` reverse proxy to
  the backend.

Environment injection via a root `.env` file. Only `GROQ_API_KEY` is required — search
defaults to DuckDuckGo, which needs no key; `TAVILY_API_KEY` is needed only when
`SEARCH_PROVIDER=tavily`.
Single command: `docker compose up --build`.

---

## 9. Future Extensions

| Phase | Enhancement | Technical impact |
|---|---|---|
| Phase 8 | Reranking step before grading | Cross-encoder rerank of top-k so the grader sees the best chunks first |
| Phase 9 | Multi-hop query decomposition | Break compound questions into sub-queries, retrieve per sub-query |
| Phase 10 | Streaming token output | Stream `generate` tokens to the frontend over SSE / WebSocket |
| Phase 11 | Hallucination-grade retry loop | If validation fails, loop back to `transform_query` instead of returning |
| Phase 12 | Evaluation harness | Measure grading accuracy, fallback precision, groundedness on a fixed set |
