# Adaptive Corrective RAG (CRAG) with Web Search Fallback

Agentic RAG system built with LangGraph that self-grades retrieved documents,
rewrites ambiguous queries, and falls back to live web search when local
context is insufficient — eliminating hallucinations from stale/irrelevant
vector store hits.

## Tech Stack
- **Orchestration:** LangGraph (StateGraph)
- **LLM/Embeddings:** LangChain + Groq / FastEmbed / HuggingFace
- **Vector Store:** ChromaDB / FAISS
- **Web Search:** Tavily Search API / DuckDuckGo Search
- **Output Validation:** Guardrails AI
- **Backend:** FastAPI (async)
- **Frontend:** React + Vite + Tailwind CSS
- **Containerization:** Docker & Docker Compose

## How it works
1. `retrieve_local` — vector similarity search against ChromaDB
2. `grade_documents` — LLM grades relevance ("yes"/"no")
3. If relevant → `generate` straight away
4. If not relevant → `transform_query` → `web_search_fallback` (Tavily) → `generate`
5. `validate_guardrails` — checks hallucination/PII/toxicity before final output

## Setup
```bash
cp .env.example .env   # fill in GROQ_API_KEY and TAVILY_API_KEY
docker-compose up --build
```

Backend: `POST /api/query`
Frontend: served via Nginx, shows source badges (Local DB vs Web Fallback)

## Roadmap
- [ ] Add reranking step before grading
- [ ] Multi-hop query decomposition
- [ ] Streaming token output to frontend
