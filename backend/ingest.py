"""Phase 1 — local documents ko Chroma me ingest karo.

Run:
    python ingest.py            # incremental (collection already bhari ho to skip)
    python ingest.py --reset    # wipe karke dobara build

Idempotent rakha hai kyunki embedding model pehli baar ~100MB download karta hai
aur re-embedding slow hai — har container start pe rebuild nahi chahiye.
"""

import argparse
import shutil
import sys
from pathlib import Path

from app.config import get_settings


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
        "--reset", action="store_true", help="existing vectorstore wipe karke rebuild"
    )
    args = parser.parse_args()

    s = get_settings()
    data_dir = Path(s.DATA_DIR)
    store_dir = Path(s.VECTORSTORE_DIR)

    if not data_dir.exists():
        print(f"[ingest] ERROR: data dir nahi mila: {data_dir}")
        return 1

    if args.reset and store_dir.exists():
        # Directory khud nahi hatate — Docker me ye ek mount point hai aur usko
        # rmtree karne pe "Device or resource busy" aata hai. Contents clear karo.
        print(f"[ingest] --reset -> clearing {store_dir}")
        for child in store_dir.iterdir():
            shutil.rmtree(child) if child.is_dir() else child.unlink()

    # get_vectorstore() lru_cache'd hai, isliye reset ke baad hi import karo
    from app.config import get_vectorstore
    from app.tools.vector_search import collection_count

    get_vectorstore.cache_clear()
    store = get_vectorstore()

    existing = store._collection.count()
    if existing and not args.reset:
        print(
            f"[ingest] collection '{s.COLLECTION_NAME}' me pehle se {existing} chunks hai. "
            "Rebuild ke liye: python ingest.py --reset"
        )
        return 0

    docs = load_documents(data_dir)
    if not docs:
        print(f"[ingest] ERROR: {data_dir} me koi .md / .txt file nahi mili")
        return 1
    print(f"[ingest] {len(docs)} documents loaded from {data_dir}")

    chunks = split_documents(docs)
    print(f"[ingest] {len(chunks)} chunks banaye (size={s.CHUNK_SIZE}, overlap={s.CHUNK_OVERLAP})")

    print(f"[ingest] embedding with {s.EMBEDDING_MODEL} (pehli baar model download hoga)...")
    store.add_documents(chunks)

    print(f"[ingest] done -> {collection_count()} chunks persisted at {store_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
