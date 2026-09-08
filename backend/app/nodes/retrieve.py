"""`retrieve` node — local knowledge base se top-k chunks.

Graph ka entry point. Yahan koi relevance ka faisla nahi hota — similarity search
hamesha k results deta hai, chahe corpus me kuch relevant ho ya na ho. Wahi naive
RAG ka core failure mode hai; uska faisla agla node (`grade_documents`) karta hai.
"""

from app.config import get_settings
from app.schemas.crag_state import CRAGState
from app.tools.vector_search import similarity_search_with_sources


def run(state: CRAGState) -> dict:
    question = state["question"]
    k = get_settings().TOP_K

    pairs = similarity_search_with_sources(question, k=k)
    documents = [text for text, _ in pairs]

    # Duplicates hata dete hain, order rakh ke: 4 chunks aksar 2 hi files se aate
    # hain, aur UI me ek hi filename do baar dikhana bekaar hai. `dict.fromkeys`
    # insertion order preserve karta hai, `set` nahi karta — order matter karta
    # hai kyunki pehla source sabse relevant chunk ka hai.
    sources = list(dict.fromkeys(source for _, source in pairs))

    return {
        # `documents` List[str] hi rehta hai. Sources alag field me isliye jaate
        # hain ki `generate` ka contract na toote — wo sirf documents padhta hai
        # aur usse farak nahi padna chahiye ki context local hai ya web ka.
        "documents": documents,
        "sources": sources,
        "source_type": "vector_db",
        "logs": [f"retrieve -> {len(documents)} chunks from vector_db (k={k})"],
    }
