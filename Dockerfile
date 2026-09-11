# Single-service deploy image: FastAPI serves both the API and the built React app.
#
# Why one container instead of two: a split deployment needs CORS configured, a
# second service to deploy, and a second thing to keep awake. Serving the SPA
# from the same origin removes all three — the app code already fetches relative
# `/api/...` paths, so nothing in the frontend changes.
#
# `backend/Dockerfile` and `frontend/Dockerfile` still exist and are what
# docker-compose uses locally, where Nginx serves the frontend separately.
#
# Target is a HuggingFace Space (Docker SDK), not Render: this backend peaks at
# 464 MB against Render free's 512 MB limit, with the cross-encoder and BM25
# index accounting for ~214 MB of it. The measurements and the reasoning for not
# simply turning those off are in docs/ROADMAP.md.
#
# Build context is the repo root:  docker build -f Dockerfile .

# ---- stage 1: build the React app ----
FROM node:20-alpine AS frontend

WORKDIR /fe

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ---- stage 2: python app, models, index, static files ----
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pull the embedding and reranker models at build time (~100 MB) so the first
# request is not the one that waits for a download, and so the container can run
# with no model-host access at all.
ENV FASTEMBED_CACHE_PATH=/app/.fastembed_cache
RUN python -c "\
from fastembed import TextEmbedding; \
from fastembed.rerank.cross_encoder import TextCrossEncoder; \
TextEmbedding(model_name='BAAI/bge-small-en-v1.5'); \
TextCrossEncoder(model_name='Xenova/ms-marco-MiniLM-L-6-v2'); \
print('embedding + reranker models cached')"

COPY backend/app ./app
COPY backend/data ./data
# eval/ ships too: /api/stats reads the measured routing numbers out of
# eval/results.json, so the Evaluation page shows real results rather than
# placeholders on a fresh deploy.
COPY backend/eval ./eval
COPY backend/ingest.py backend/main.py ./
COPY --from=frontend /fe/dist ./static

# Build the Chroma index into the image rather than copying a prebuilt one.
#
# `backend/vectorstore/` is gitignored, so on a fresh clone — which is exactly
# what a Space builds from — there would be nothing to copy and the app would
# boot with an empty index. Building it here needs only `data/`, which *is* in
# git, and it keeps the index from ever drifting from the corpus it claims to
# represent. It costs about 12 MB and a few seconds.
RUN python ingest.py --corpus concepts && \
    python -c "\
from app.tools.vector_search import collection_count; \
n = collection_count(); \
print(f'indexed {n} chunks'); \
assert n > 0, 'ingest produced an empty index'"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# HuggingFace Spaces routes to 7860 by default; Render and most PaaS inject
# $PORT. Shell form so it expands, with a default that keeps plain `docker run`
# working locally.
EXPOSE 7860
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}"]
