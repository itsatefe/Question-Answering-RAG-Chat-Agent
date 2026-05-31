"""
RAG Pipeline — load, chunk, embed, store, and retrieve research papers.

Pipeline overview:
  1. Load  : read PDFs from documents/
  2. Chunk : split into overlapping text windows
  3. Embed : turn each chunk into a vector using a local sentence-transformer
  4. Store : persist vectors in ChromaDB on disk
  5. Query : at runtime, embed the user question and find the closest chunks
"""

from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ── Paths ─────────────────────────────────────────────────────────────────────

DOCUMENTS_DIR = Path(__file__).parent / "documents"
VECTOR_STORE_DIR = Path(__file__).parent / "vector_store"

# ── Embedding model ────────────────────────────────────────────────────────────
# all-MiniLM-L6-v2: small (80 MB), fast, good at semantic similarity.
# Downloaded once from HuggingFace and cached locally (~/.cache/huggingface/).
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# ── Chunking settings ──────────────────────────────────────────────────────────
# Research papers are dense, so we use larger chunks than typical web content.
# overlap=200 means consecutive chunks share 200 characters — this prevents
# an answer from being split exactly at a chunk boundary.
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def _load_documents():
    """Step 1 — Load every PDF in the documents/ folder."""
    pdf_files = list(DOCUMENTS_DIR.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDFs found in {DOCUMENTS_DIR}")

    all_docs = []
    for pdf_path in pdf_files:
        print(f"  Loading: {pdf_path.name}")
        loader = PyPDFLoader(str(pdf_path))
        # PyPDFLoader returns one Document per page, with metadata like
        # {"source": "path/to/file.pdf", "page": 3}
        all_docs.extend(loader.load())

    print(f"  → {len(all_docs)} pages loaded from {len(pdf_files)} PDF(s)")
    return all_docs


def _chunk_documents(docs):
    """Step 2 — Split pages into smaller overlapping chunks.

    RecursiveCharacterTextSplitter tries to split on paragraph breaks first,
    then sentences, then words — so chunks stay semantically coherent.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(docs)
    print(f"  → {len(chunks)} chunks created (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    return chunks


def _get_embeddings():
    """Return the local HuggingFace embedding model (downloaded on first use)."""
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)


def build_vector_store():
    """Steps 1-4 — Build and persist the vector store from scratch.

    Call this once (or whenever you add new documents).
    Saves the ChromaDB index to vector_store/ on disk.
    """
    print("Building vector store...")
    docs = _load_documents()
    chunks = _chunk_documents(docs)

    print(f"  Embedding {len(chunks)} chunks with {EMBEDDING_MODEL}...")
    print("  (First run downloads the model ~80 MB — takes a minute)")

    # Chroma.from_documents embeds every chunk and saves the index to disk.
    # persist_directory means the index survives restarts — no re-embedding needed.
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=_get_embeddings(),
        persist_directory=str(VECTOR_STORE_DIR),
    )
    print(f"  → Vector store saved to {VECTOR_STORE_DIR}")
    return vector_store


def _load_vector_store():
    """Load an existing vector store from disk (fast — no re-embedding)."""
    return Chroma(
        persist_directory=str(VECTOR_STORE_DIR),
        embedding_function=_get_embeddings(),
    )


def remove_document_from_store(pdf_path: Path) -> None:
    """Remove all chunks belonging to a PDF from the vector store."""
    if not VECTOR_STORE_DIR.exists():
        return
    store = _load_vector_store()
    store.delete(where={"source": str(pdf_path)})


def add_document_to_store(pdf_path: Path) -> int:
    """Embed a single PDF and add its chunks to the vector store.

    Creates the store from scratch if it doesn't exist yet.
    Returns the number of chunks embedded.
    """
    loader = PyPDFLoader(str(pdf_path))
    docs = loader.load()
    chunks = _chunk_documents(docs)
    embeddings = _get_embeddings()

    if not VECTOR_STORE_DIR.exists():
        Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=str(VECTOR_STORE_DIR),
        )
    else:
        store = _load_vector_store()
        store.add_documents(chunks)

    return len(chunks)


def get_retriever(k: int = 4):
    """Step 5 (setup) — Return a retriever that finds the top-k relevant chunks.

    k=4 means we fetch the 4 most semantically similar chunks to the query.
    More chunks = more context for the LLM, but also more tokens.
    """
    if not VECTOR_STORE_DIR.exists():
        print("Vector store not found — building it now...")
        build_vector_store()

    vector_store = _load_vector_store()
    # as_retriever() wraps the vector store in a standard LangChain interface.
    # search_type="similarity" uses cosine distance between query and chunk vectors.
    return vector_store.as_retriever(search_type="similarity", search_kwargs={"k": k})


# ── The ADK tool function ──────────────────────────────────────────────────────

_retriever = None

# Stores the raw LangChain Document objects from the last search_documents call.
# The Streamlit UI reads this after the agent responds to show source proof.
_last_retrieved_docs: list = []


def get_last_retrieved_docs() -> list:
    """Return the chunks retrieved during the most recent search_documents call."""
    return list(_last_retrieved_docs)


def search_documents(query: str) -> str:
    """Search the research paper documents for information relevant to the query.

    Use this tool whenever the user asks a question that could be answered
    from the research papers in the documents folder.

    Args:
        query: The user's question or topic to look up.

    Returns:
        Relevant excerpts from the documents, with source and page number.
    """
    global _retriever, _last_retrieved_docs
    if _retriever is None:
        _retriever = get_retriever()

    docs = _retriever.invoke(query)
    _last_retrieved_docs = docs  # save for UI display

    if not docs:
        return "No relevant information found in the research papers."

    parts = []
    for i, doc in enumerate(docs, 1):
        source = Path(doc.metadata.get("source", "unknown")).name
        page = doc.metadata.get("page", "?")
        parts.append(
            f"[Excerpt {i} — {source}, page {page + 1}]\n{doc.page_content.strip()}"
        )

    return "\n\n---\n\n".join(parts)


# ── CLI helper ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run this file directly to build the vector store:
    #   python rag_pipeline.py
    build_vector_store()
    print("\nDone. Run agent_client.py to start chatting.")
