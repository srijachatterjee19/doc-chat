#!/usr/bin/env python3
"""FastAPI backend exposing the RAG chatbot as a streaming HTTP API."""
import json
from contextlib import asynccontextmanager
from pathlib import Path

import ollama
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.embeddings import EmbeddingModel
from src.rag import RAGChatbot
from src.vector_store import VectorStore

load_dotenv()

_embedding_model: EmbeddingModel
_vector_store: VectorStore
_chatbot: RAGChatbot


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _embedding_model, _vector_store, _chatbot
    _embedding_model = EmbeddingModel()
    _vector_store = VectorStore()
    _chatbot = RAGChatbot(_embedding_model, _vector_store)
    yield


app = FastAPI(title="RAG Chatbot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    model: str = "llama3.2"


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


@app.get("/api/status")
def status():
    """Return the number of ingested document chunks."""
    return {"doc_count": _vector_store.count()}


@app.get("/api/models")
def models():
    """Return available Ollama chat models."""
    return {"models": _get_chat_models()}


@app.post("/api/chat")
def chat(request: ChatRequest):
    """Stream a RAG-augmented chat response as SSE."""
    if _chatbot.model != request.model:
        _chatbot.model = request.model
        _chatbot.reset()

    def generate():
        for chunk in _chatbot.chat(request.message):
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/reset")
def reset():
    """Clear the chatbot's conversation history."""
    _chatbot.reset()
    return {"ok": True}


# Serve the production React build when it exists
_static_dir = Path(__file__).parent / "frontend" / "dist"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
