"""Phase 1 — local documents ko Chroma me ingest karo.

Run:
    python ingest.py            # incremental (collection already bhari ho to skip)
    python ingest.py --reset    # wipe karke dobara build

Idempotent rakha hai kyunki embedding model pehli baar ~100MB download karta hai
aur re-embedding slow hai — har container start pe rebuild nahi chahiye.
"""

import argparse
import sys
from pathlib import Path

from app.config import get_settings, get_vectorstore


def load_documents(data_dir: Path):
    """data/ ki .md aur .txt files padho.

    data/README.md skip hota hai — wo corpus ka part nahi, uske baare me notes hai.
    Usko ingest karna corpus me "yahan kya nahi hai" wala meta-text daal deta,
    jo grader ko confuse karta.
    """
    from langchain_core.documents import Document

    docs = []
    for path in sorted(data_dir.iterdir()):
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        if path.name.lower() == "readme.md":
            continue
        docs.append(
            Document(
                page_content=path.read_text(encoding="utf-8"),
                metadata={"source": path.name},
            )
        )
    return docs


def load_beir_documents(name: str = "scifact", limit: int = 0):
    """BEIR corpus ko Documents me badlo.

    Har abstract ek Document hai, `title` text ke aage jodte hain — SciFact ke
    titles claim-jaise hote hain aur retrieval me kaam ke signal hain, unhe
    phenkna information waste karna hoga.

    `source` metadata me `doc_id` jaata hai, filename nahi — citations aur qrels
    dono usi id pe milte hain, isliye eval verify kar sakta hai ki jo doc
    retrieve hua wo sach me gold doc tha.
    """
    from langchain_core.documents import Document

    from app.tools.beir_loader import load_corpus

    return [
        Document(
            page_content=f"{title}\n\n{text}" if title else text,
            metadata={"source": doc_id, "title": title},
        )
        for doc_id, title, text in load_corpus(name, limit=limit)
        if text.strip()
    ]


def split_documents(docs):
    """Recursive character splitting — heading/paragraph boundaries pe todta hai
    fixed character count pe nahi, taaki related text saath rahe."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    s = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=s.CHUNK_SIZE,
        chunk_overlap=s.CHUNK_OVERLAP,
        separators=["\n## ", "\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(docs)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest local docs into Chroma")
    parser.add_argument(
        "--reset", action="store_true", help="existing collection wipe karke rebuild"
    )
    parser.add_argument(
        "--corpus", default="", choices=["", "concepts", "scifact"],
        help="kaunsa corpus ingest karna hai (default: CORPUS env / concepts)",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="sirf pehle N documents (smoke run ke liye, BEIR pe)",
    )
    args = parser.parse_args()

    s = get_settings()
    if args.corpus:
        s.CORPUS = args.corpus
        # collection_name CORPUS se derive hota hai, to cached store stale hai
        get_vectorstore.cache_clear()

    store_dir = Path(s.VECTORSTORE_DIR)
    store = get_vectorstore()

    # **Sirf is corpus ki collection reset hoti hai, poori directory nahi.**
    # Dono corpora ek hi `vectorstore/` me alag collections me rehte hain —
    # directory wipe karne se doosra corpus bhi ud jaata aur usko dobara embed
    # karna padta (SciFact pe wo minutes ka kaam hai).
    if args.reset:
        print(f"[ingest] --reset -> dropping collection '{s.collection_name}'")
        try:
            store._client.delete_collection(s.collection_name)
        except Exception:  # noqa: BLE001 — collection pehle se na ho
            pass
        get_vectorstore.cache_clear()
        store = get_vectorstore()

    from app.tools.vector_search import collection_count

    existing = store._collection.count()
    if existing and not args.reset:
        print(
            f"[ingest] collection '{s.collection_name}' me pehle se {existing} chunks hai. "
            "Rebuild ke liye: python ingest.py --reset"
        )
        return 0

    if s.CORPUS == "scifact":
        print("[ingest] corpus: BEIR SciFact")
        docs = load_beir_documents("scifact", limit=args.limit)
    else:
        data_dir = Path(s.DATA_DIR)
        if not data_dir.exists():
            print(f"[ingest] ERROR: data dir nahi mila: {data_dir}")
            return 1
        print("[ingest] corpus: concepts (backend/data/)")
        docs = load_documents(data_dir)
    if not docs:
        print(f"[ingest] ERROR: corpus '{s.CORPUS}' se koi document nahi mila")
        return 1
    print(f"[ingest] {len(docs)} documents loaded")

    chunks = split_documents(docs)
    print(f"[ingest] {len(chunks)} chunks banaye (size={s.CHUNK_SIZE}, overlap={s.CHUNK_OVERLAP})")

    print(f"[ingest] embedding with {s.EMBEDDING_MODEL} ...")

    # **Batch me add karte hain.** Chroma ka apna max batch size hai (~5.4k) aur
    # SciFact usse kaafi upar jaata hai — poora list ek baar me dena wahan
    # crash karta. Batching se progress bhi dikhta hai, jo 10k chunks pe zaroori
    # hai warna lagta hai script hang ho gayi.
    BATCH = 2000
    for i in range(0, len(chunks), BATCH):
        store.add_documents(chunks[i : i + BATCH])
        done = min(i + BATCH, len(chunks))
        print(f"[ingest]   {done}/{len(chunks)} chunks embedded", flush=True)

    # BM25 index poore corpus se banta hai aur lru_cache me rehta hai. Ingestion
    # ke baad wo stale hai — clear na karo to same process me purana index chalta rahe.
    from app.tools.bm25_search import bust_cache

    bust_cache()

    print(f"[ingest] done -> {collection_count()} chunks persisted at {store_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
