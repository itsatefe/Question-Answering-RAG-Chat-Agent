"""
FastAPI backend — wraps the existing agent + RAG pipeline.
Exposes SSE streaming chat + document management endpoints.

Run with:
    uvicorn fastapi_app:app --reload --port 8000
"""

import json
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent_client import create_agent_client
from rag_pipeline import (
    list_documents,
    add_document,
    delete_document,
    get_index_stats,
    rebuild_index,
    _get_embeddings,
)
from session_utils import create_session
from config import USER_ID

try:
    from google.adk.errors.session_not_found_error import SessionNotFoundError
except ImportError:
    SessionNotFoundError = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()
    # Load embedding model and agent client in background threads so the
    # server is fully ready before the first request arrives.
    await loop.run_in_executor(None, _get_embeddings)
    await loop.run_in_executor(None, get_agent_client)
    yield


app = FastAPI(title="RAG Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single shared agent client (same as Streamlit app does)
_agent_client = None


def get_agent_client():
    global _agent_client
    if _agent_client is None:
        _agent_client = create_agent_client()
    return _agent_client


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class SessionResponse(BaseModel):
    session_id: str


@app.post("/api/session", response_model=SessionResponse)
def new_session():
    client = get_agent_client()
    session_id = create_session(client, user_id=USER_ID)
    return {"session_id": session_id}


# ---------------------------------------------------------------------------
# Chat — SSE streaming
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    session_id: str
    message: str


async def _stream_agent(session_id: str, message: str) -> AsyncIterator[str]:
    """
    Yields Server-Sent Events.
    Each event is either:
      data: {"type": "text", "content": "..."}
      data: {"type": "artifact", "content": "<full html string>"}
      data: {"type": "session_reset", "session_id": "..."}
      data: {"type": "done"}
    """
    client = get_agent_client()

    loop = asyncio.get_event_loop()

    def _sync_stream(sid: str):
        return list(client.stream_query(
            user_id=USER_ID,
            session_id=sid,
            message=message,
        ))

    try:
        events = await loop.run_in_executor(None, lambda: _sync_stream(session_id))
    except Exception as exc:
        if SessionNotFoundError and isinstance(exc, SessionNotFoundError):
            new_session_id = create_session(client, user_id=USER_ID)
            yield f"data: {json.dumps({'type': 'session_reset', 'session_id': new_session_id})}\n\n"
            events = await loop.run_in_executor(None, lambda: _sync_stream(new_session_id))
        else:
            raise

    full_text = ""
    for event in events:
        content = event.get("content", {}) if isinstance(event, dict) else getattr(event, "content", {})
        parts = content.get("parts", []) if isinstance(content, dict) else getattr(content, "parts", [])
        for part in parts:
            text = part.get("text", "") if isinstance(part, dict) else getattr(part, "text", "")
            if text:
                full_text += text

    # Parse artifacts out of the full response.
    # Agent wraps content in: <artifact type="react">...</artifact>
    # or legacy:              <artifact type="html">...</artifact>
    import re
    artifact_pattern = re.compile(r'<artifact\s+type=["\']?(\w+)["\']?>(.*?)</artifact>', re.DOTALL)
    artifacts = [(m.group(1), m.group(2).strip()) for m in artifact_pattern.finditer(full_text)]
    clean_text = artifact_pattern.sub("", full_text).strip()

    if clean_text:
        yield f"data: {json.dumps({'type': 'text', 'content': clean_text})}\n\n"

    for artifact_type, artifact_content in artifacts:
        yield f"data: {json.dumps({'type': 'artifact', 'artifactType': artifact_type, 'content': artifact_content})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@app.post("/api/chat")
async def chat(req: ChatRequest):
    return StreamingResponse(
        _stream_agent(req.session_id, req.message),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@app.get("/api/documents")
def get_documents():
    docs = list_documents()
    return {"documents": docs}


@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    content = await file.read()
    result = add_document(file.filename, content)
    return {"message": f"Uploaded and indexed {file.filename}", "result": result}


@app.delete("/api/documents/{filename}")
def remove_document(filename: str):
    delete_document(filename)
    return {"message": f"Deleted {filename}"}


@app.get("/api/index/stats")
def index_stats():
    return get_index_stats()


@app.post("/api/index/rebuild")
def rebuild():
    rebuild_index()
    return {"message": "Index rebuilt"}
