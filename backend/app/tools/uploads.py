"""User-uploaded documents: parse, chunk, and index into a per-session corpus.

Why per-session rather than into the main index: two people using the deployed
demo would otherwise see each other's documents, and a query would retrieve from
a corpus the asker never supplied. Each upload gets its own Chroma collection
keyed by a session id, so the retriever can only see what that session added.

The collections live on the container's filesystem, which on Cloud Run is
ephemeral - an uploaded document survives until the instance is recycled. That
is the correct lifetime for a demo and the wrong one for a product; making it
durable means object storage plus a real vector database, which is a different
project.

Text extraction is pypdf for PDFs and a plain decode for text. No OCR: a scanned
PDF yields no text layer, and returning an empty document silently would look
like a retrieval failure rather than an unsupported input, so it raises.
"""

from __future__ import annotations

import io
import re
import unicodedata

from app.config import get_embeddings, get_settings

# Generous enough for a book chapter, small enough that one request cannot fill
# the container's disk. A 150-page PDF is roughly 1-2 MB of text.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_PAGES = 400

SUPPORTED = {".pdf", ".md", ".txt"}


class UploadError(ValueError):
    """Raised for inputs the API should reject with a 4xx, not a 500."""


def session_collection(session_id: str) -> str:
    """Chroma collection name for one session's uploads.

    Sanitised because the id reaches Chroma, which requires an alphanumeric
    name, and because it arrives from the client.
    """
    clean = re.sub(r"[^a-zA-Z0-9]", "", session_id)[:32]
    if len(clean) < 3:
        raise UploadError("session id must be at least 3 alphanumeric characters")
    return f"crag_upload_{clean}"


def extract_text(filename: str, blob: bytes) -> str:
    """Plain text from a supported upload, or raise UploadError."""
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in SUPPORTED:
        raise UploadError(f"unsupported file type '{suffix or filename}' - use PDF, MD or TXT")
    if len(blob) > MAX_UPLOAD_BYTES:
        raise UploadError(f"file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")

    if suffix != ".pdf":
        try:
            return blob.decode("utf-8")
        except UnicodeDecodeError:
            return blob.decode("latin-1", errors="replace")

    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(blob))
    except Exception as exc:  # noqa: BLE001 - a corrupt PDF is user error, not a bug
        raise UploadError(f"could not read that PDF: {exc}") from exc

    if reader.is_encrypted:
        raise UploadError("that PDF is password protected")
    if len(reader.pages) > MAX_PAGES:
        raise UploadError(f"that PDF has {len(reader.pages)} pages; the limit is {MAX_PAGES}")

    pages = [(page.extract_text() or "") for page in reader.pages]
    text = "\n\n".join(p for p in pages if p.strip())
    if not text.strip():
        # Almost always a scan. Saying so beats indexing nothing and letting the
        # user conclude that retrieval is broken.
        raise UploadError(
            "no text layer in that PDF - it is probably a scan, and OCR is not supported"
        )
    return text


def normalise(text: str) -> str:
    """Collapse the whitespace PDF extraction leaves behind.

    pypdf emits a newline per layout line, so a paragraph arrives pre-broken.
    Left alone the splitter treats those as boundaries and chunks end mid
    sentence, which measurably hurts retrieval.
    """
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[ \t]+", " ", text)
    # A single newline inside a paragraph is a layout artefact; two or more is a
    # real break.
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def ingest_upload(session_id: str, filename: str, blob: bytes) -> dict:
    """Parse, chunk and index one upload. Returns a summary for the API."""
    from langchain_chroma import Chroma
    from langchain_core.documents import Document
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    settings = get_settings()
    text = normalise(extract_text(filename, blob))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_text(text)
    if not chunks:
        raise UploadError("that file produced no text to index")

    store = Chroma(
        collection_name=session_collection(session_id),
        embedding_function=get_embeddings(),
        persist_directory=settings.VECTORSTORE_DIR,
    )
    store.add_documents(
        [
            Document(page_content=c, metadata={"source": filename, "chunk": i})
            for i, c in enumerate(chunks)
        ]
    )

    return {
        "filename": filename,
        "chunks": len(chunks),
        "characters": len(text),
        "total_chunks": store._collection.count(),
    }


def clear_session(session_id: str) -> None:
    """Drop everything a session uploaded. Used by the UI's reset."""
    import chromadb

    client = chromadb.PersistentClient(path=get_settings().VECTORSTORE_DIR)
    try:
        client.delete_collection(session_collection(session_id))
    except Exception:  # noqa: BLE001 - nothing uploaded yet is not an error
        pass
