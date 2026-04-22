from collections.abc import Generator

import ollama

from .embeddings import EmbeddingModel
from .history import ChatHistory
from .vector_store import VectorStore

SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on provided context documents.

When answering:
- Use only information from the provided context
- If the context doesn't contain enough information, say so clearly
- Be concise and accurate
- Cite relevant parts of the context when helpful

After every answer, add a new line followed by:
**You might also ask:**
- [suggestion 1]
- [suggestion 2]
- [suggestion 3]

Suggestions must be related to the document context and follow naturally from the current question."""


class RAGChatbot:
    """Multi-turn chatbot that grounds responses in retrieved document context."""

    def __init__(
        self,
        embedding_model: EmbeddingModel,
        vector_store: VectorStore,
        model: str = "llama3.2",
    ):
        self.client = ollama.Client()
        self.model = model
        self.embedding_model = embedding_model
        self.vector_store = vector_store
        self._db = ChatHistory()
        # Load persisted history on startup; clean (no injected context) so turns stay stable
        self.history: list[dict] = self._db.load()

    def _rewrite_query(self, user_message: str) -> str:
        """Rewrite the user message as a standalone search query using recent history."""
        if not self.history:
            return user_message

        history_text = "\n".join(
            f"{m['role'].capitalize()}: {m['content']}" for m in self.history[-6:]
        )
        prompt = (
            f"Conversation so far:\n{history_text}\n\n"
            f"Rewrite the following question as a concise standalone search query "
            f"that captures the full intent, incorporating any context from the conversation. "
            f"Return only the rewritten query, nothing else.\n\n"
            f"Question: {user_message}\nStandalone query:"
        )
        response = self.client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )
        return response.message.content.strip()

    def _retrieve_context(self, query: str, n_results: int = 3) -> str:
        """Embed the query and return top-n document chunks as a formatted string."""
        query_embedding = self.embedding_model.embed_single(query)
        docs = self.vector_store.query(query_embedding, n_results=n_results)
        if not docs:
            return ""
        return "\n\n".join(f"[Document {i + 1}]\n{doc}" for i, doc in enumerate(docs))

    def stream(self, user_message: str) -> Generator[str, None, None]:
        """Yield response tokens. Caller must call commit() after exhausting this generator."""
        # Save user message immediately so a mid-stream refresh doesn't lose it
        self._db.append("user", user_message)

        retrieval_query = self._rewrite_query(user_message)
        context = self._retrieve_context(retrieval_query)

        augmented_message = (
            f"Context:\n{context}\n\nQuestion: {user_message}" if context else user_message
        )

        messages = (
            [{"role": "system", "content": SYSTEM_PROMPT}]
            + self.history
            + [{"role": "user", "content": augmented_message}]
        )

        for chunk in self.client.chat(model=self.model, messages=messages, stream=True):
            yield chunk.message.content

    def commit(self, user_message: str, assistant_response: str) -> None:
        """Persist a completed exchange to memory and the database."""
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": assistant_response})
        self._db.append("assistant", assistant_response)

    def reset(self) -> None:
        """Clear conversation history from memory and the database."""
        self.history = []
        self._db.clear()
