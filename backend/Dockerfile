# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# Copy requirements first so the pip install layer stays cached when code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# FastEmbed model (~100MB) build time pe hi pull kar lo, taaki pehli request /
# pehla ingest slow na ho aur container offline bhi chal jaye.
ENV FASTEMBED_CACHE_PATH=/app/.fastembed_cache
RUN python -c "\
from fastembed import TextEmbedding; \
from fastembed.rerank.cross_encoder import TextCrossEncoder; \
TextEmbedding(model_name='BAAI/bge-small-en-v1.5'); \
TextCrossEncoder(model_name='Xenova/ms-marco-MiniLM-L-6-v2'); \
print('fastembed embedding + reranker models cached')"

COPY app/ ./app/
COPY data/ ./data/
# eval/ is needed too: `/api/stats` reads routing numbers out of
# `eval/results.json`, and `python -m eval.run_eval` runs inside the container.
COPY eval/ ./eval/
COPY ingest.py main.py ./

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
