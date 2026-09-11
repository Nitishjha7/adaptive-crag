"""Phase 1 — local documents ko Chroma me ingest karo.

Run:
    python ingest.py            # incremental (collection already bhari ho to skip)
    python ingest.py --reset    # wipe karke dobara build

Kept idempotent because the embedding model downloads ~100 MB on first use and
re-embedding is slow — a rebuild on every container start is not wanted.
"""

import argparse
import sys
from pathlib import Path

from app.config import get_settings, get_vectorstore


def load_documents(data_dir: Path):
    """data/ ki .md aur .txt files padho.

    data/README.md is skipped — it is notes *about* the corpus, not part of it.
    Ingesting it would put "what is not in here" meta-text into the corpus, which
    is exactly the sort of thing that confuses the grader.
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
    discarding it would throw away information.

    `source` metadata holds the `doc_id`, not a filename — citations and qrels
    both key on that id, so the eval can verify that the document
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
    rather than a fixed character count, so related text stays together."""
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
        help="which corpus to ingest (default: CORPUS env, else concepts)",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="corpus subset: saare gold docs + filler, total N (0 = poora)",
    )
    args = parser.parse_args()

    s = get_settings()
    if args.corpus:
        s.CORPUS = args.corpus
        # collection_name CORPUS se derive hota hai, to cached store stale hai
        get_vectorstore.cache_clear()

    store_dir = Path(s.VECTORSTORE_DIR)
    store = get_vectorstore()

    # **Only this corpus's collection is reset, not the whole directory.**
    # Dono corpora ek hi `vectorstore/` me alag collections me rehte hain —
    # Wiping the directory would take the other corpus with it and force a
    # re-embed, which on SciFact costs minutes.
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
            print(f"[ingest] ERROR: data dir not found: {data_dir}")
            return 1
        print("[ingest] corpus: concepts (backend/data/)")
        docs = load_documents(data_dir)
    if not docs:
        print(f"[ingest] ERROR: no documents found for corpus '{s.CORPUS}'")
        return 1
    print(f"[ingest] {len(docs)} documents loaded")
    print(f"[ingest] embedding with {s.EMBEDDING_MODEL} ...")

    # **Streaming: split aur embed dono batch-wise.**
    #
    # Pehle poora corpus split karke saare chunks ek list me rakhe the — SciFact
    # pe wo 17,266 chunks banti hai aur container (3.5 GB) **OOM se mar gaya**
    # (exit 137). Never visible on the concepts corpus and its 22 chunks.
    #
    # Ab documents ke batch pe kaam hota hai: split -> embed -> chhod do. Peak
    # memory stops scaling with corpus size, so larger corpora also
    # chalenge.
    DOC_BATCH = 50
    total_chunks = 0

    for i in range(0, len(docs), DOC_BATCH):
        batch_chunks = split_documents(docs[i : i + DOC_BATCH])
        if not batch_chunks:
            continue
        store.add_documents(batch_chunks)
        total_chunks += len(batch_chunks)
        print(
            f"[ingest]   {min(i + DOC_BATCH, len(docs))}/{len(docs)} docs "
            f"-> {total_chunks} chunks",
            flush=True,
        )

    print(f"[ingest] {total_chunks} chunks total "
          f"(size={s.CHUNK_SIZE}, overlap={s.CHUNK_OVERLAP})")

    # BM25 index poore corpus se banta hai aur lru_cache me rehta hai. Ingestion
    # ke baad wo stale hai — clear na karo to same process me purana index chalta rahe.
    from app.tools.bm25_search import bust_cache

    bust_cache()

    print(f"[ingest] done -> {collection_count()} chunks persisted at {store_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
