# Adaptive Corrective RAG (CRAG) with Web Search Fallback
### Project Documentation — Overview, Working, USP, Demo & Interview Guide

> Note: Isme project ka pura context cover kiya hai *except* build/setup commands
> (wo already README aur setup-flow doc me hai). Ye doc samjhne, demo karne aur
> interview me explain karne ke liye hai.

---

## 1. Project Kya Hai (One-liner)

**Full form:** Adaptive Corrective Retrieval-Augmented Generation

Ek agentic RAG system jo naive RAG ke "blind retrieval trust" problem ko solve karta hai —
retrieved documents ko **self-grade** karta hai, agar irrelevant/insufficient lage toh
query **rewrite** karke **live web search** se fresh context laata hai, aur final answer
ko **guardrails** se validate karke deta hai.

Ek line me: *"RAG jo apni khud ki galti pakadta hai aur khud fix karta hai — bina hamesha
web search pe depend kiye, sirf jab zaroorat ho tab."*

---

## 2. Problem Statement (Why this exists)

Traditional/naive RAG systems ek assumption pe kaam karte hain: **jo bhi vector DB se
retrieve hua, wo relevant hai.** Isse do major issues aate hain:

1. **Hallucination** — agar retrieved chunks query se match nahi karte, LLM phir bhi
   unse "kuch na kuch" answer bana deta hai, jo galat hota hai.
2. **Staleness** — agar local knowledge base outdated hai (naya event, naya data),
   system purani/wrong info de deta hai kyunki usko pata hi nahi ki uska data insufficient hai.

CRAG in dono problems ko **verification-first approach** se solve karta hai.

---

## 3. Tech Stack

| Layer | Technology | Responsibility |
|---|---|---|
| Agent Orchestration | LangGraph (StateGraph) | Conditional branching, stateful workflow, corrective loops |
| LLM & Embeddings | LangChain + Groq / FastEmbed / HuggingFace | Relevance grading, embeddings, answer synthesis |
| Local Knowledge Base | ChromaDB / FAISS | Vector storage & similarity search |
| Web Search Fallback | Tavily Search API / DuckDuckGo | Live fallback when local docs graded irrelevant |
| Output Validation | Guardrails AI | Hallucination, PII leakage, toxicity checks |
| Backend | FastAPI (async) | REST API, retrieval scores, execution logs |
| Frontend | React + Vite + Tailwind CSS | Chat UI, source badges, relevance indicators |
| Containerization | Docker & Docker Compose | Unified backend + vector DB + frontend deployment |

---

## 4. How It Works — Step by Step

```
User Query
    |
    v
Retrieve Context (Vector DB)
    |
    v
Grade Documents (LLM relevance check: yes/no)
    |
    +--- Relevant -----------------> Generate Answer
    |
    +--- Irrelevant/Low Score --> Rewrite Query --> Web Search (Tavily)
                                        --> Generate Answer (Web Context)
    |
    v
Guardrail Validation (hallucination / PII / toxicity check)
    |
    v
Final Output (with source badge: Local DB / Web Fallback)
```

**Node-by-node:**

| Node | What it does |
|---|---|
| `retrieve_local` | Vector similarity search against ChromaDB (cosine distance) |
| `grade_documents` | LLM binary grader — is retrieved context sufficient? yes/no |
| `transform_query` | If "no" — rewrites natural language query into search-optimized keywords |
| `web_search_fallback` | Queries Tavily/DuckDuckGo with transformed query; replaces local docs |
| `generate` | Synthesizes answer grounded strictly in verified context |
| `validate_guardrails` | Final scan for hallucination, PII leakage, toxic content |

**State object (`CRAGState`)** tracks everything end-to-end: original question,
transformed query, documents, relevance score, source type (vector_db/web_search),
raw generation, final validated output, and full execution logs.

---

## 5. USP — Kya Alag Hai Isme

1. **Self-Grading** — System khud check karta hai retrieval ka kaam ka hai ya nahi,
   answer banane se pehle. Koi blind trust nahi.
2. **Autonomous Fallback** — Agar local knowledge insufficient hai, khud decide karke
   live web se fresh data laata hai. User ko manually "search web" bolna nahi padta.
3. **Guardrails Layer** — Final output bhi double-check hota hai before showing —
   hallucination/PII/toxicity ka extra safety net.
4. **Adaptive routing** — Fixed pipeline nahi; runtime pe decide hota hai kaunsa
   path lena hai based on grading — isliye "Adaptive" naam me hai.

---

## 6. Demo Strategy

Core idea: judges/interviewer ko sirf "chat dikh raha hai" nahi lagna chahiye —
**decision-making live** dikhani hai (grading → routing → fallback → validation).

### Scenario 1 — Happy Path (Local DB sufficient)
- Kuch specific docs pehle se ingest karke rakho (5–10 docs, controlled set)
- Us document se directly related query pucho
- Flow: `retrieve_local` → `grade_documents: YES` → `generate` → answer with
  **"Source: Local Vector DB"** badge
- **Talking point:** "Jab local knowledge sufficient hai, unnecessary web call nahi
  hota — fast aur cheap."

### Scenario 2 — Correction Path (asli USP yahi hai)
- Aisi query pucho jiska local DB me answer hi nahi hai (deliberately ek "gap" rakho dataset me)
- Flow: `grade_documents: NO` → `transform_query` (rewritten query dikhao) →
  `web_search_fallback` triggered → `generate` → **"Source: Web Fallback"** badge
- **Talking point:** "System khud decide kar raha hai ki local pe trust nahi karna,
  aur khud correct kar raha hai — bina user input ke."

### Scenario 3 — Guardrail Catch (agar time ho)
- Koi tricky/ambiguous query jisse hallucination risk ho
- Guardrails layer output validate karte hue dikhao

### UI me kya highlight karna hai
- **Source badge** (Local DB vs Web Fallback) har answer ke sath
- **Execution trace / step logs** — kaunsa node chala, kis order me (sabse impressive part — explainability dikhata hai)
- **Relevance score** transparently dikhana (yes/no)

### Practical tip
Demo/recording ke liye chhota controlled dataset use karo taaki fallback trigger
predictable ho — live demo me randomness avoid karo. Portfolio ke liye trace logs
ka screenshot zaroor rakho.

---

## 7. Interview Pitch Script

**Step 1 — Problem (30 sec):**
"Traditional RAG systems ek blind assumption pe kaam karte hain — jo bhi vector
database se retrieve hota hai, wo relevant maan liya jaata hai. Isse retrieval
mismatch pe hallucination hoti hai, aur outdated local data pe stale answers milte hain."

**Step 2 — Solution (1 min):**
"Maine ek Adaptive Corrective RAG system banaya jo self-verification se ye solve
karta hai. Query aati hai, local vector store se retrieve hota hai, ek grading
step LLM se check karta hai relevance. Agar relevant hai, direct answer. Agar
nahi, system khud query rewrite karta hai aur live web search (Tavily) trigger
karta hai fresh context ke liye. Final output guardrails layer se validate hota
hai hallucination/PII/toxicity ke liye."

**Step 3 — Why this architecture:**
"LangGraph isliye use kiya kyunki mujhe conditional branching chahiye thi — simple
chain nahi, ek graph jahan system runtime pe decide kare kaunsa path lena hai based
on grading output. State object pura execution trace maintain karta hai."

**Step 4 — Technical depth (if asked):**
- Grading = binary classifier LLM call ("yes"/"no" relevance)
- Guardrails AI ensures final answer sirf verified context se grounded ho, LLM
  apni training knowledge se kuch add na kare

**Step 5 — Closing USP line:**
"System apni khud ki galti pakadta hai aur khud correct karta hai — bina hamesha
web search pe depend kiye. Verification-first approach naive retrieval-blind-trust
se zyada reliable hai."

### Likely Follow-up Questions

| Question | Answer angle |
|---|---|
| Web search hamesha kyu nahi karte? | Cost + latency — local hit fast hai, fallback sirf zaroorat pe |
| Production deploy kaise karoge? | FastAPI backend + Docker Compose, vector DB persistence volume, React frontend Nginx behind reverse proxy |
| Scaling ka kya plan? | Local vector DB ko managed service (Pinecone/Weaviate) pe migrate karna production scale ke liye |
| SQL agent se collide toh nahi karta? | Nahi — dono "self-correcting agentic loop" pattern share karte hain but alag domains me: SQL agent execution errors fix karta hai, CRAG retrieval relevance verify/correct karta hai. Ye ek coherent skill-area story banata hai portfolio me. |

---

## 8. Positioning Alongside Other Projects

Portfolio me isko isolated project ki tarah nahi, ek **pattern** ki tarah present karo:

> "Agentic Self-Correcting Systems" — jisme Self-Healing SQL Agent (execution-error
> correction) aur Adaptive CRAG (retrieval-relevance correction) dono aate hain.

Ye recruiter ko dikhata hai ki tumhe sirf ek trick nahi aati — balki tum ek
architectural pattern (LLM + self-verification + autonomous correction) ko
different domains me apply kar sakte ho.

---

## 9. Quick Reference — CRAGState Schema

```python
class CRAGState(TypedDict):
    question: str            # Original user query
    transformed_query: str   # Web-optimized search query
    documents: List[str]     # Retrieved chunks (Local or Web)
    relevance_score: str     # "yes" or "no"
    source_type: str         # "vector_db" or "web_search"
    generation: str          # Raw synthesized answer
    final_output: str        # Guardrail-validated final response
    logs: List[str]          # Node trace execution logs
```
