#!/usr/bin/env python3
"""Streamlit web UI for the RAG chatbot."""
import ollama
import streamlit as st
from dotenv import load_dotenv

from src.embeddings import EmbeddingModel
from src.rag import RAGChatbot
from src.vector_store import VectorStore

load_dotenv()

st.set_page_config(page_title="RAG Chatbot", page_icon="🤖", layout="centered")
st.title("🤖 RAG Chatbot")


@st.cache_resource
def load_base() -> tuple[EmbeddingModel, VectorStore]:
    """Initialise and cache the embedding model and vector store across reruns."""
    return EmbeddingModel(), VectorStore()


def get_chat_models() -> list[str]:
    """Return Ollama models suitable for chat, excluding embedding-only models."""
    try:
        models = []
        for m in ollama.list().models:
            families = m.details.families or []
            # Embedding models report bert/nomic-bert in families
            if not any("bert" in f for f in families):
                models.append(m.model)
        return models or ["llama3.2"]
    except Exception:
        return ["llama3.2"]


embedding_model, vector_store = load_base()

doc_count = vector_store.count()
if doc_count == 0:
    st.warning(
        "No documents ingested yet. Run `python ingest.py data/sample.txt` to load documents.",
        icon="⚠️",
    )
else:
    st.caption(f"📚 {doc_count} document chunks loaded")

# Initialise session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chatbot" not in st.session_state:
    st.session_state.chatbot = RAGChatbot(embedding_model, vector_store)

# Sidebar controls
with st.sidebar:
    st.header("Settings")

    available_models = get_chat_models()
    selected_model = st.selectbox("Ollama model", available_models)

    if selected_model != st.session_state.chatbot.model:
        st.session_state.chatbot = RAGChatbot(embedding_model, vector_store, model=selected_model)
        st.session_state.messages = []

    st.markdown("---")
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.chatbot.reset()
        st.rerun()

    st.markdown("---")
    st.markdown("**Add documents**")
    st.code("python ingest.py path/to/file.txt", language="bash")

# Render chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask a question about your documents..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response = st.write_stream(st.session_state.chatbot.chat(prompt))

    st.session_state.messages.append({"role": "assistant", "content": response})
