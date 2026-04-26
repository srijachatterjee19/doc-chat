#!/usr/bin/env python3
"""FastAPI backend exposing the RAG chatbot as a streaming HTTP API."""
import json
import logging
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import ollama
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .ingest import ingest_file, read_file

_BLOCKED_TERMS: frozenset[str] = frozenset({
    "fuck", "fucking", "fucker", "shit", "bitch", "cunt", "dick", "pussy",
    "nigger", "nigga", "bastard", "whore", "slut", "asshole", "motherfucker",
    "faggot", "retard", "twat", "cock", "piss", "crap",
})

_FREE_PLAN_WORD_LIMIT = 10_000


def _contains_profanity(text: str) -> bool:
    return bool(_BLOCKED_TERMS & set(re.findall(r"\b[a-z]+\b", text.lower())))
from .src.rag import RAGChatbot
from .src.vector_store import VectorStore
from .src.analytics import init_db, log_event, get_dau, get_retention, get_funnel

load_dotenv()

limiter = Limiter(key_func=get_remote_address)


# --- Structured JSON logging ---

class _JsonFormatter(logging.Formatter):
    _SKIP = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        data: dict = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "message": record.message,
        }
        for key, val in record.__dict__.items():
            if key not in self._SKIP:
                data[key] = val
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data)


_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter())
logger = logging.getLogger("api")
logger.setLevel(logging.INFO)
logger.addHandler(_handler)
logger.propagate = False

_vector_store: VectorStore
_chatbot: RAGChatbot


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _vector_store, _chatbot
    init_db()
    _vector_store = VectorStore()
    _chatbot = RAGChatbot(_vector_store)
    yield


app = FastAPI(title="RAG Chatbot API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def track_requests(request: Request, call_next):
    request_id = uuid4().hex[:8]
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        "%s %s",
        request.method,
        request.url.path,
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "client_ip": request.client.host if request.client else None,
        },
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Duration-Ms"] = str(duration_ms)
    return response


class ChatRequest(BaseModel):
    message: str
    model: str = "llama3.2"
    rewrite_query: bool = True


def _get_chat_models() -> list[str]:
    """Return Ollama models suitable for chat, excluding embedding-only models."""
    try:
        models = []
        for m in ollama.list().models:
            families = m.details.families or []
            if not any("bert" in f for f in families):
                models.append(m.model)
        return models or ["llama3.2"]
    except Exception:
        return ["llama3.2"]


@app.get("/api/history")
def history():
    """Return the persisted conversation history."""
    return {"messages": _chatbot.history}


@app.get("/api/status")
def status():
    """Return the number of ingested document chunks."""
    return {"doc_count": _vector_store.count()}


@app.get("/api/documents")
def documents():
    """Return all ingested source files and their chunk counts."""
    return {"documents": _vector_store.list_sources()}


@app.get("/api/models")
def models():
    """Return available Ollama chat models."""
    return {"models": _get_chat_models()}


@app.post("/api/chat")
@limiter.limit("20/minute")
def chat(request: Request, body: ChatRequest):
    """Stream a RAG-augmented chat response as SSE."""
    if _chatbot.model != body.model:
        _chatbot.model = body.model
        _chatbot.reset()

    def generate():
        if _contains_profanity(body.message):
            msg = "I'm not able to respond to messages containing abusive language. Please keep the conversation respectful."
            yield f"data: {json.dumps({'text': msg})}\n\ndata: [DONE]\n\n"
            return

        full_response = ""
        stream_start = time.perf_counter()
        first_token_ms: float | None = None
        for chunk in _chatbot.stream(body.message, rewrite_query=body.rewrite_query):
            if isinstance(chunk, dict):
                chunk_type = chunk.get("type")
                if chunk_type == "agent_update":
                    yield f"data: {json.dumps(chunk)}\n\n"
                elif chunk_type == "text":
                    if first_token_ms is None:
                        first_token_ms = round((time.perf_counter() - stream_start) * 1000, 1)
                    full_response += chunk["text"]
                    yield f"data: {json.dumps({'text': chunk['text']})}\n\n"
            else:
                # Ollama fallback yields raw strings
                if first_token_ms is None:
                    first_token_ms = round((time.perf_counter() - stream_start) * 1000, 1)
                full_response += chunk
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        if full_response:
            _chatbot.commit(body.message, full_response)
            logger.info(
                "chat completed",
                extra={
                    "event": "chat",
                    "model": body.model,
                    "message_chars": len(body.message),
                    "response_chars": len(full_response),
                    "first_token_ms": first_token_ms,
                    "total_stream_ms": round((time.perf_counter() - stream_start) * 1000, 1),
                },
            )
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/reset")
@limiter.limit("10/minute")
def reset(request: Request):
    """Clear the chatbot's conversation history."""
    _chatbot.reset()
    return {"ok": True}


@app.post("/api/history/rollback")
def history_rollback():
    """Remove the last message when it is an orphaned user turn with no assistant reply."""
    _chatbot._db.rollback_last()
    if _chatbot.history and _chatbot.history[-1]["role"] == "user":
        _chatbot.history.pop()
    return {"ok": True}


_UPLOADS_DIR = Path(__file__).parent.parent / "uploads"
_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


@app.post("/api/upload")
@limiter.limit("5/minute")
async def upload(request: Request, file: UploadFile = File(...)):
    """Ingest an uploaded document and save the original to uploads/."""
    if not file.filename.endswith((".txt", ".md", ".pdf")):
        raise HTTPException(status_code=400, detail="Only .txt, .md, and .pdf files are supported.")
    content = await file.read()
    if len(content) > _MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 10 MB limit.")

    dest_path = _UPLOADS_DIR / file.filename
    _UPLOADS_DIR.mkdir(exist_ok=True)
    dest_path.write_bytes(content)
    try:
        text_content = read_file(dest_path)
    except Exception:
        text_content = ""
    word_count = len(text_content.split())
    if word_count > _FREE_PLAN_WORD_LIMIT:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=402,
            detail=f"This document contains {word_count:,} words, which exceeds the {_FREE_PLAN_WORD_LIMIT:,}-word limit on your current plan. Upgrade to Pro to upload larger documents.",
        )

    ingest_file(str(dest_path), _vector_store)
    doc_count = _vector_store.count()
    logger.info(
        "document ingested",
        extra={
            "event": "upload",
            "filename": file.filename,
            "file_bytes": len(content),
            "doc_count": doc_count,
        },
    )
    return {"ok": True, "doc_count": doc_count}


@app.get("/api/files/{filename}")
async def serve_file(filename: str):
    """Serve an uploaded file by name."""
    path = _UPLOADS_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    from fastapi.responses import FileResponse
    media_type = "application/pdf" if filename.lower().endswith(".pdf") else "text/plain"
    return FileResponse(path, media_type=media_type, headers={"Content-Disposition": "inline"})


class EventRequest(BaseModel):
    event: str
    user_id: str | None = None
    properties: dict = {}


@app.post("/api/metrics/event")
def track_event(body: EventRequest):
    """Log a frontend analytics event to the database."""
    log_event(body.event, body.user_id, body.properties)
    return {"ok": True}


@app.get("/api/metrics/dau")
def dau(days: int = 30):
    """Daily active users for the last N days."""
    return {"dau": get_dau(days)}


@app.get("/api/metrics/retention")
def retention(days: int = 30):
    """Day-7 retention by cohort for the last N days."""
    return {"retention": get_retention(days)}


@app.get("/api/metrics/funnel")
def funnel():
    """Conversion funnel: landing → signup → login → first_message → upgrade."""
    return {"funnel": get_funnel()}


@app.post("/api/payments/subscribe")
def sandbox_subscribe():
    """Sandbox: instantly grant Pro tier without a real payment."""
    return {"tier": "pro"}


# Serve the production React build when it exists
_static_dir = Path(__file__).parent.parent / "frontend" / "dist"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
