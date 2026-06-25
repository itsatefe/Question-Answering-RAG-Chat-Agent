from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

DOCUMENTS_DIR = Path(__file__).parent / "documents"
VECTOR_STORE_DIR = Path(__file__).parent / "vector_store"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def _load_documents():
    pdf_files = list(DOCUMENTS_DIR.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDFs found in {DOCUMENTS_DIR}")

    all_docs = []
    for pdf_path in pdf_files:
        print(f"  Loading: {pdf_path.name}")
        loader = PyPDFLoader(str(pdf_path))
        all_docs.extend(loader.load())

    print(f"  → {len(all_docs)} pages loaded from {len(pdf_files)} PDF(s)")
    return all_docs


def _chunk_documents(docs):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(docs)
    print(f"  → {len(chunks)} chunks created (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    return chunks


def _get_embeddings():
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)


def build_vector_store():
    print("Building vector store...")
    docs = _load_documents()
    chunks = _chunk_documents(docs)

    print(f"  Embedding {len(chunks)} chunks with {EMBEDDING_MODEL}...")
    print("  (First run downloads the model ~80 MB — takes a minute)")

    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=_get_embeddings(),
        persist_directory=str(VECTOR_STORE_DIR),
    )
    print(f"  → Vector store saved to {VECTOR_STORE_DIR}")
    return vector_store


def _load_vector_store():
    return Chroma(
        persist_directory=str(VECTOR_STORE_DIR),
        embedding_function=_get_embeddings(),
    )


def remove_document_from_store(pdf_path: Path) -> None:
    if not VECTOR_STORE_DIR.exists():
        return
    store = _load_vector_store()
    store.delete(where={"source": str(pdf_path)})


def add_document_to_store(pdf_path: Path) -> int:
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


def list_documents() -> list:
    return [p.name for p in sorted(DOCUMENTS_DIR.glob("*.pdf"))]


def add_document(filename: str, content: bytes) -> int:
    DOCUMENTS_DIR.mkdir(exist_ok=True)
    pdf_path = DOCUMENTS_DIR / filename
    pdf_path.write_bytes(content)
    return add_document_to_store(pdf_path)


def delete_document(filename: str) -> None:
    pdf_path = DOCUMENTS_DIR / filename
    remove_document_from_store(pdf_path)
    if pdf_path.exists():
        pdf_path.unlink()


def get_index_stats() -> dict:
    if not VECTOR_STORE_DIR.exists():
        return {"documents": 0, "chunks": 0, "indexed": False}
    store = _load_vector_store()
    count = store._collection.count()
    return {"documents": len(list_documents()), "chunks": count, "indexed": True}


def rebuild_index() -> None:
    import shutil
    if VECTOR_STORE_DIR.exists():
        shutil.rmtree(VECTOR_STORE_DIR)
    build_vector_store()


def get_retriever(k: int = 4):
    if not VECTOR_STORE_DIR.exists():
        print("Vector store not found — building it now...")
        build_vector_store()

    vector_store = _load_vector_store()
    return vector_store.as_retriever(search_type="similarity", search_kwargs={"k": k})


_retriever = None
_last_retrieved_docs: list = []


def get_last_retrieved_docs() -> list:
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
    _last_retrieved_docs = docs

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


if __name__ == "__main__":
    build_vector_store()
    print("\nDone. Run agent_client.py to start chatting.")
