# Setup Guide — Adaptive CRAG

Running it, the loops you work in, and every error this project actually hit.

---

## 1. Prerequisites

| | |
|---|---|
| **Docker Desktop** | Everything runs in containers — see the note in §4 |
| **A Groq API key** | Free at [console.groq.com/keys](https://console.groq.com/keys). The only key required |
| Web search | Nothing to do — DuckDuckGo is the default provider and needs no key |

Roughly 2 GB of free disk: the backend image is 1.3 GB, mostly the embedding and
cross-encoder models baked in at build time so the first query is not the one that
waits for a download.

---

## 2. First run

```bash
cp .env.example .env      # then put the real key in GROQ_API_KEY
docker compose up --build
```

- **UI** → <http://localhost:3001>
- **API docs** → <http://localhost:8001/docs>

Ports are 3001/8001 rather than 3000/8000 because other projects commonly hold those.
Override `FRONTEND_PORT` / `BACKEND_PORT` in `.env`.

Two containers come up: `backend` (FastAPI + LangGraph + embedded Chroma, with
`vectorstore/` mounted as a volume) and `frontend` (the React build served by Nginx,
proxying `/api/`). **Chroma is not a separate service** — it runs embedded, and all it
needs for persistence is that mounted directory.

---

## 3. Check it actually works

```bash
curl http://localhost:8001/health
# {"status":"ok","indexed_chunks":22,...}
```

`indexed_chunks: 0` means the index is empty — see §5.

Then run one query down each route, because they exercise different code:

| Question | Expected |
|---|---|
| *Why does chunk overlap matter when splitting documents?* | Local DB badge, `grade: yes` |
| *What is the Model Context Protocol?* | Web Fallback badge, `grade: no` |

The second one is the point of the project: the corpus contains no MCP
material, so the grader rejects the retrieved chunks and the system searches instead
of guessing.

---

## 4. The loops you work in

`dev.ps1` runs everything in the backend container with the source bind-mounted, so
an edit needs no rebuild. It is faster than `docker compose` for backend work.

```powershell
.\dev.ps1 build              # only when requirements.txt changes
.\dev.ps1 ask "why does chunk overlap matter?"
.\dev.ps1 test               # 124 tests, no API key needed
.\dev.ps1 eval               # routing eval — real LLM and live web calls
.\dev.ps1 eval --limit 6     # smoke run, saves rate limit
.\dev.ps1 serve -Port 8042   # FastAPI alone
```

> **Why everything is in Docker:** there is no Python on the machine this was built on
> — only a WindowsApps stub. `dev.ps1` exists to wrap that away. With a local Python
> install, `pip install -r backend/requirements.txt` then `python -m app "..."` and
> `pytest` work directly.

---

## 5. Ingestion and switching corpus

The index is built offline, — there is no upload endpoint.

```powershell
.\dev.ps1 ingest             # embed backend/data/ into Chroma
.\dev.ps1 ingest -Reset      # wipe and rebuild
```

Two corpora live in separate Chroma collections, so their numbers can never mix:

```bash
CORPUS=scifact docker compose up -d --build   # BEIR SciFact, 1,717 chunks
docker compose up -d                          # back to concepts
```

**Stop compose before a large ingest.** A running backend holds the same
`vectorstore/`, and SQLite lock contention makes the ingest hang silently rather than
fail — see §6.

---

## 6. Errors this project actually hit

Each of these cost real time. They are listed so they cost less the next time.

**`model_not_found` (404) from Groq.** `llama-3.3-70b-versatile` no longer exists.
Model ids get retired; check before a demo:

```bash
curl https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY"
```

Put whatever id comes back in `LLM_MODEL`. No mock catches this, which is the argument
for running against the real API before trusting anything.

**`ingest.py --reset` fails with `Device or resource busy`.** `vectorstore/` is a mount
point inside the container, so `rmtree` cannot remove it. The script clears the
contents instead; if you hit this in your own code, do the same.

**502 on the first query after `docker compose up`.** Nginx came up before uvicorn had
bound. Fixed by `depends_on: condition: service_healthy` rather than
`service_started` — `/health` makes no LLM call, so it is a cheap and reliable gate.

**A large ingest hangs with no error.** SQLite lock contention: a running compose
backend holds the same store. Stop compose first.

**Exit 137 during SciFact ingestion.** An OOM kill — 17,266 chunks did not fit in
3.5 GB. Ingestion now streams per batch, so peak memory no longer scales with corpus
size.

**Queries get slower the more you run.** Groq throttles under sustained load, badly
enough that it once made a latency comparison in the eval look like a real result when
it was an artifact. If you are timing anything, this is the first thing to rule out.

---

## 7. A rule learned the hard way

**`.env.example` is committed. `.env` is not.**

A real Groq key once reached `.env.example` and was pushed to a public repository. It
was revoked, purged from the git history of all three projects, and the remotes
force-pushed — then verified from a fresh clone. Revoking is the part that actually
matters; rewriting history does not un-leak a key that has already been cloned.

Placeholders only in `.env.example`, always.

---

## 8. Where to go next

| | |
|---|---|
| [PROJECT_WALKTHROUGH.md](PROJECT_WALKTHROUGH.md) | **Start here** — how a request flows, and how the system was built |
| [backend/eval/RESULTS.md](../backend/eval/RESULTS.md) | Every measurement, including the negative ones |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Deploying to Cloud Run, and the memory measurements behind the sizing |
| [ROADMAP.md](ROADMAP.md) | What exists, what does not, what is next |
