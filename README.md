# Research Paper Q&A Agent

A RAG-based chat agent that lets you upload research papers (PDFs) and ask questions about them. The agent only answers from your documents — no hallucination from model memory.

## What it does

- Upload PDFs via a Streamlit sidebar
- Each document is chunked, embedded, and stored in a local vector database
- Ask questions in a chat interface; the agent retrieves relevant excerpts and cites the source file and page number
- Delete documents and their chunks are immediately removed from the index

## Tech stack

| Layer | Technology |
|---|---|
| UI | Streamlit |
| Agent | Google ADK + Gemini 2.5 Flash Lite |
| RAG pipeline | LangChain (loader, splitter, retriever) |
| Vector DB | ChromaDB (local, on disk) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (runs locally) |
| Session storage | In-memory (default) or PostgreSQL |

## How to run

**1. Install dependencies**
```bash
pip install google-adk
pip install -r requirements-rag.txt
```

**2. Set up environment**

Create a `.env` file:
```
PROJECT_ID=your-gcp-project-id
```

Authentication uses [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials) — run `gcloud auth application-default login` once and your logged-in account is used automatically.

**3. Build the vector store (optional)**

If you already have PDFs in the `documents/` folder:
```bash
python rag_pipeline.py
```

**4. Start the app**
```bash
streamlit run streamlit_app.py
```

Then open `http://localhost:8501`, upload a PDF, and start chatting.
