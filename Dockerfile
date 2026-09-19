# Single-service deploy image: FastAPI serves the API and the built React app
# from one origin, so there is no CORS to configure and one service to deploy.
# docker-compose uses backend/Dockerfile and frontend/Dockerfile instead, where
# Nginx serves the frontend separately.
#
# Build from the repo root: docker build -f Dockerfile .

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

# Models are pulled at build time (~100 MB) so the first request does not wait
# for a download, and the container needs no model-host access at runtime.
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
# eval/results.json, so the Evaluation page shows real results on a fresh deploy.
COPY backend/eval ./eval
COPY backend/ingest.py backend/main.py ./
COPY --from=frontend /fe/dist ./static

# The index is built here rather than copied in. backend/vectorstore/ is
# gitignored, so a fresh clone has nothing to copy and the app would boot with
# an empty index. Building needs only data/, which is in git, and keeps the
# index from drifting from the corpus it represents. Costs ~12 MB.
RUN python ingest.py --corpus concepts && \
    python -c "\
from app.tools.vector_search import collection_count; \
n = collection_count(); \
print(f'indexed {n} chunks'); \
assert n > 0, 'ingest produced an empty index'"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Cloud Run and most PaaS inject $PORT. Shell form so it expands; the default
# keeps plain `docker run` working locally.
EXPOSE 8080
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
