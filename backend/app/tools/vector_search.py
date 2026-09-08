"""Chroma similarity search wrapper.

`retrieve` node aur ingestion script dono isi ke through jaate hain — k /
score-threshold tuning ek hi jagah rehti hai, do jagah drift nahi hoti.
"""

from typing import List, Optional, Tuple

from app.config import get_settings, get_vectorstore


def similarity_search(query: str, k: Optional[int] = None) -> List[str]:
    """Top-k chunks ka plain text return karta hai.

    Node ko Document objects nahi chahiye — `CRAGState.documents` List[str] hai,
    taaki web snippets aur local chunks ek hi shape me rahein aur `generate` ko
    source se farak na pade.
    """
    k = k or get_settings().TOP_K
    docs = get_vectorstore().similarity_search(query, k=k)
    return [d.page_content for d in docs]


def similarity_search_with_scores(query: str, k: Optional[int] = None):
    """Debugging / eval ke liye — (text, distance) pairs.

    Chroma cosine me **distance** deta hai (0 = identical), similarity nahi.
    Ye production path me use nahi hota: relevance ka faisla LLM grader karta
    hai, koi score threshold nahi — threshold tune karna corpus-specific aur
    brittle hota hai.
    """
    k = k or get_settings().TOP_K
    return [
        (d.page_content, score)
        for d, score in get_vectorstore().similarity_search_with_score(query, k=k)
    ]


def similarity_search_with_sources(
    query: str, k: Optional[int] = None
) -> List[Tuple[str, str]]:
    """Top-k chunks `(text, source)` pairs ki tarah.

    `source` wo filename hai jo ingestion ne metadata me daala tha
    (`ingest.py` -> `metadata={"source": path.name}`). Wo metadata pehle se store
    ho raha tha, bas kabhi padha nahi jaata tha — citations ke liye wahi chahiye.

    Alag function hai, `similarity_search` badla nahi, kyunki wo eval aur tests
    dono me use hota hai aur unko sirf text chahiye.
    """
    k = k or get_settings().TOP_K
    docs = get_vectorstore().similarity_search(query, k=k)
    return [(d.page_content, d.metadata.get("source", "unknown")) for d in docs]


def collection_count() -> int:
    """Kitne chunks index me hain — ingestion verify karne ke liye."""
    return get_vectorstore()._collection.count()
