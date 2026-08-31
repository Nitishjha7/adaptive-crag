# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# requirements pehle copy — code badalne pe pip install layer cached rehti hai
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# FastEmbed model (~100MB) build time pe hi pull kar lo, taaki pehli request /
# pehla ingest slow na ho aur container offline bhi chal jaye.
ENV FASTEMBED_CACHE_PATH=/app/.fastembed_cache
RUN python -c "\
from fastembed import TextEmbedding; \
TextEmbedding(model_name='BAAI/bge-small-en-v1.5'); \
print('fastembed model cached')"

COPY app/ ./app/
COPY data/ ./data/
COPY ingest.py main.py ./

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Phase 5 me main.py bharega. Tab tak image `python -m app "..."` ke liye use hoti hai.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
