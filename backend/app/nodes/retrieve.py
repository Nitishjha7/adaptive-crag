"""`retrieve` node — local knowledge base se top-k chunks.

Graph ka entry point. Yahan koi relevance ka faisla nahi hota — similarity search
hamesha k results deta hai, chahe corpus me kuch relevant ho ya na ho. Wahi naive
RAG ka core failure mode hai; uska faisla agla node (`grade_documents`) karta hai.
"""

from app.config import get_settings
from app.schemas.crag_state import CRAGState
from app.tools.vector_search import similarity_search


def run(state: CRAGState) -> dict:
    question = state["question"]
    k = get_settings().TOP_K

    documents = similarity_search(question, k=k)

    return {
        "documents": documents,
        "source_type": "vector_db",
        "logs": [f"retrieve -> {len(documents)} chunks from vector_db (k={k})"],
    }
