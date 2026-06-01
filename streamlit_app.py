from pathlib import Path

import streamlit as st

from agent_client import create_agent_client
from config import USER_ID
from rag_pipeline import (
    DOCUMENTS_DIR,
    VECTOR_STORE_DIR,
    add_document_to_store,
    remove_document_from_store,
    build_vector_store,
    get_last_retrieved_docs,
)
import rag_pipeline
from session_utils import create_session, send_message

st.set_page_config(
    page_title="Research Q&A Agent",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .doc-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; }
    .doc-name { flex: 1; font-size: 0.85rem; overflow: hidden;
                text-overflow: ellipsis; white-space: nowrap; }
    .stChatMessage { border-radius: 8px; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _init():
    if "agent_client" not in st.session_state:
        with st.spinner("Starting agent..."):
            st.session_state.agent_client = create_agent_client()

    if "session_id" not in st.session_state:
        st.session_state.session_id = create_session(
            st.session_state.agent_client,
            user_id=USER_ID,
        )

    if "messages" not in st.session_state:
        st.session_state.messages = []

    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)


_init()

with st.sidebar:
    st.title("📚 Document Library")

    pdf_files = sorted(DOCUMENTS_DIR.glob("*.pdf"))

    if pdf_files:
        st.caption(f"{len(pdf_files)} document{'s' if len(pdf_files) != 1 else ''} in library")
        for pdf in pdf_files:
            col_name, col_del = st.columns([5, 1])
            with col_name:
                size_kb = pdf.stat().st_size // 1024
                st.markdown(f"**{pdf.name}**  \n`{size_kb} KB`")
            with col_del:
                if st.button("🗑", key=f"del_{pdf.name}", help=f"Delete {pdf.name}"):
                    remove_document_from_store(pdf)
                    pdf.unlink()
                    rag_pipeline._retriever = None
                    st.toast(f"Deleted {pdf.name} and removed its chunks from the index.", icon="🗑")
                    st.rerun()
    else:
        st.info("No documents yet.")

    st.divider()

    st.subheader("Upload PDF")
    uploaded = st.file_uploader(
        "Drop a research paper here",
        type=["pdf"],
        label_visibility="collapsed",
    )

    if uploaded is not None:
        dest = DOCUMENTS_DIR / uploaded.name
        if dest.exists():
            st.warning(f"`{uploaded.name}` is already in the library.")
        else:
            with st.spinner(f"Chunking & embedding `{uploaded.name}`…"):
                dest.write_bytes(uploaded.read())
                try:
                    n_chunks = add_document_to_store(dest)
                    rag_pipeline._retriever = None  # force retriever refresh
                    st.success(f"Added **{uploaded.name}** — {n_chunks} chunks indexed.")
                except Exception as exc:
                    dest.unlink(missing_ok=True)
                    st.error(f"Embedding failed: {exc}")
            st.rerun()

    st.divider()

    with st.expander("Index management"):
        store_exists = VECTOR_STORE_DIR.exists()
        st.caption(f"Vector store: {'✅ exists' if store_exists else '❌ not built'}")

        if st.button("🔨 Rebuild full index", use_container_width=True):
            if not list(DOCUMENTS_DIR.glob("*.pdf")):
                st.error("No PDFs in the library to index.")
            else:
                with st.spinner("Rebuilding vector store from all documents…"):
                    try:
                        build_vector_store()
                        rag_pipeline._retriever = None
                        st.success("Index rebuilt successfully.")
                    except Exception as exc:
                        st.error(f"Build failed: {exc}")
                st.rerun()

    st.divider()

    if st.button("🔄 New conversation", use_container_width=True):
        st.session_state.session_id = create_session(
            st.session_state.agent_client,
            user_id=USER_ID,
        )
        st.session_state.messages = []
        st.rerun()

    st.caption(f"Session `{st.session_state.session_id}`")


st.title("Research Paper Q&A")
st.caption("Ask anything about the documents in your library. The agent will search and cite sources.")


def _render_sources(sources: list):
    if not sources:
        return
    with st.expander(f"📎 {len(sources)} source excerpt(s) retrieved from the paper"):
        for i, doc in enumerate(sources, 1):
            source = Path(doc.metadata.get("source", "unknown")).name
            page = doc.metadata.get("page", 0) + 1  # PDFs are 0-indexed internally
            st.markdown(f"**Excerpt {i} — `{source}`, page {page}**")
            st.text(doc.page_content.strip())
            if i < len(sources):
                st.divider()


if not st.session_state.messages:
    st.info(
        "Start by uploading a PDF in the sidebar, then ask a question below.",
        icon="💡",
    )

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
    if msg["role"] == "assistant" and msg.get("sources"):
        _render_sources(msg["sources"])

if prompt := st.chat_input("Ask about your research papers…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            response = send_message(
                st.session_state.agent_client,
                user_id=USER_ID,
                session_id=st.session_state.session_id,
                message=prompt,
            )
        st.markdown(response or "_No response from agent._")

    sources = get_last_retrieved_docs()
    _render_sources(sources)

    st.session_state.messages.append({
        "role": "assistant",
        "content": response or "",
        "sources": sources,
    })
