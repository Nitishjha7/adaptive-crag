# Project Setup Guide — Adaptive CRAG

Ye document project ko scratch se set up karne ke sare steps cover karta hai — git init se
lekar GitHub pe push karne tak. Jo commands actually chali thi wahi yahan documented hai.

> **Sections 1–9 historical record hai** — ye tab chale the jab repo Linux pe `~/Music` me
> banaya gaya tha. Ab project `d:\nitish new\agentic_ai\adaptive-crag` (Windows) pe hai.
> Inko dobara chalane ki zaroorat nahi; project chalane ke liye seedha
> [Local run](#local-run) pe jao.

## 1. Folder banao aur git init karo

```bash
cd ~/Music
mkdir adaptive-crag
cd adaptive-crag
git init
```

## 2. Folder structure banao

```bash
mkdir -p backend/app/graph
mkdir -p backend/app/nodes
mkdir -p backend/app/tools
mkdir -p backend/app/schemas
mkdir -p backend/app/guardrails
mkdir -p backend/vectorstore
mkdir -p frontend/src/components
mkdir -p frontend/src/pages

touch backend/requirements.txt backend/Dockerfile backend/main.py
touch backend/app/__init__.py backend/app/config.py
touch backend/app/graph/__init__.py backend/app/graph/state.py backend/app/graph/build_graph.py
touch backend/app/nodes/{__init__,retrieve,grade_documents,transform_query,web_search_fallback,generate,validate_guardrails}.py
touch backend/app/tools/{__init__,tavily_search,vector_search}.py
touch backend/app/schemas/__init__.py backend/app/schemas/crag_state.py
touch backend/app/guardrails/__init__.py backend/app/guardrails/validators.py

touch frontend/Dockerfile
touch docker-compose.yml .env.example .gitignore README.md
```

## 3. .gitignore banao

```bash
cat > .gitignore << 'EOF'
venv/
__pycache__/
*.pyc
node_modules/
dist/
.env
*.db
*.log
chroma_db/
faiss_index/
EOF
```

## 4. .env.example banao

```bash
cat > .env.example << 'EOF'
GROQ_API_KEY=
TAVILY_API_KEY=
VECTOR_DB=chroma
EOF
```

Real secrets (`.env`) `.gitignore` me hai — sirf `.env.example` commit hota hai (template,
bina real values ke).

## 5. Git user email set karo

Personal account ke liye email set karna zaroori hai (thinkcurve email se commit na chala jaye).

```bash
git config user.email "nitishkj5019@gmail.com"
```

## 6. Main branch rename + pehla commit

```bash
git branch -M main
git add .
git commit -m "Initial project scaffold - Adaptive CRAG"
```

## 7. GitHub pe naya empty repo banao

Browser me `https://github.com/new` — naam `adaptive-crag`, **bina** README/gitignore/license,
warna push ke time history clash hoga.

## 8. Remote add karo (SSH alias ke saath)

`~/.ssh/config` me multiple GitHub accounts ke liye alias set hai (`github-personal`),
isliye remote ko **SSH format** me set karo, `https://` mat use karo alias ke saath.

```bash
git remote add origin git@github-personal:Nitishjha7/adaptive-crag.git
git push -u origin main
```

## 9. Editor kholo

```bash
code .
```

---

## Common Error: "Port number was not a decimal number"

```
fatal: unable to access 'https://github-personal:Nitishjha7/...': URL rejected:
Port number was not a decimal number between 0 and 65535
```

SSH alias galti se `https://` ke saath mix ho gaya. Fix:

```bash
git remote remove origin
git remote add origin git@github-personal:Nitishjha7/adaptive-crag.git
git push -u origin main
```

## Common Error: "Repository not found"

GitHub pe repo abhi bana nahi hai ya SSH key register nahi hui. Pehle browser me empty repo
banao, phir dobara push.

---

## Phase-wise branches (optional, interview me acha dikhta hai)

```bash
git checkout -b feature/phase-1-vectorstore
git checkout main
git checkout -b feature/phase-2-langgraph-skeleton
git checkout main
git checkout -b feature/phase-3-grading-webfallback
git checkout main
git checkout -b feature/phase-4-guardrails
git checkout main
git checkout -b feature/phase-5-fastapi
git checkout main
git checkout -b feature/phase-6-frontend
git checkout main
```

Commit message convention (conventional commits):

```
feat(vectorstore): ingest local docs into chroma with fastembed embeddings
feat(graph):       define CRAGState schema and langgraph stategraph skeleton
feat(nodes):       implement retrieve and generate nodes
feat(grading):     add llm binary relevance grader with conditional edge
feat(transform):   rewrite query into search-optimized keywords
feat(websearch):   add duckduckgo fallback behind a provider switch, swap docs and source_type
feat(guardrails):  add groundedness + pii validation node
feat(api):         expose POST /api/query with step execution logs
feat(frontend):    react + vite + tailwind chat ui with source badges and trace
```

---

## Local run

**Sirf `GROQ_API_KEY` chahiye.** Web search default DuckDuckGo hai — koi key nahi maangta.

```bash
cp .env.example .env      # GROQ_API_KEY bharo
docker compose up --build
```

- Frontend → <http://localhost:3001>
- Backend Swagger → <http://localhost:8001/docs>

Ports 3001/8001 hain 3000/8000 nahi — is machine pe wo doosre projects ke containers le
rakhe hain. `.env` me `FRONTEND_PORT` / `BACKEND_PORT` se badal sakte ho.

Containers: `backend` (FastAPI + LangGraph + embedded Chroma, `vectorstore/` volume mounted),
`frontend` (React build Nginx se serve, `/api/` proxy). **Chroma alag service nahi hai** —
embedded mode me chalta hai, persistence ke liye bas ek mounted volume.

### Vectorstore khaali ho to

```powershell
.\dev.ps1 ingest          # backend/data/ ko Chroma me embed karta hai
.\dev.ps1 ingest -Reset   # wipe karke dobara
```

### Backend-only dev loop

`docker compose` se tez hai kyunki code bind-mount hota hai — edit ke baad rebuild nahi:

```powershell
.\dev.ps1 build              # sirf jab requirements.txt badle
.\dev.ps1 ask "why does chunk overlap matter?"
.\dev.ps1 test               # 27 tests
.\dev.ps1 serve -Port 8042   # akela FastAPI
```

> **Note:** is machine pe local Python installed nahi hai (sirf WindowsApps stub). Isliye
> har cheez Docker ke andar chalti hai — `dev.ps1` wahi wrap karta hai. Agar tu local Python
> install kar le, to `pip install -r backend/requirements.txt` ke baad seedha
> `python -m app "..."` aur `pytest` chala sakta hai.

## Deployment Plan (free tier)

| Piece | Kahan | Kyun |
|---|---|---|
| Backend (FastAPI) | [Render](https://render.com) / [Railway](https://railway.app) | Docker se deploy, free tier |
| Vector DB | Chroma persistent volume ya [Chroma Cloud](https://www.trychroma.com) | Local persistence kaafi hai demo ke liye |
| LLM | [Groq](https://console.groq.com) | Free tier, bahut fast inference |
| Web search | DuckDuckGo (default) — koi key nahi. [Tavily](https://tavily.com) optional | Signup ke bina chalta hai; Tavily behtar snippets deta hai |
| Frontend | [Vercel](https://vercel.com) / [Netlify](https://netlify.com) | Free static, GitHub auto-deploy |

**Gotchas:**
- Render free tier sleep hota hai — demo se pehle URL warm kar lena.
- Groq rate limits — demo ke liye fixed queries use karo (`backend/data/README.md`).
- **`.env` kabhi commit mat karna — aur `.env.example` me kabhi asli key mat daalna.** Wo
  file commit hoti hai. Ek baar aisa ho chuka hai aur key GitHub pe chali gayi thi; usko
  console se revoke karke nayi banani padi.
