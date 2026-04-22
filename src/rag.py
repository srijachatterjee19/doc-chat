from collections.abc import Generator

import ollama

from .embeddings import EmbeddingModel
from .vector_store import VectorStore

SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on provided context documents.

When answering:
- Use only information from the provided context
- If the context doesn't contain enough information, say so clearly
- Be concise and accurate
- Cite relevant parts of the context when helpful"""


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
        # Clean history (no injected context) so prior turns stay stable
        self.history: list[dict] = []

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

    def chat(self, user_message: str) -> Generator[str, None, None]:
        """Stream a response, prepending retrieved context to the current user turn only."""
        retrieval_query = self._rewrite_query(user_message)
        context = self._retrieve_context(retrieval_query)

        # Inject context only into the current turn — history stays clean
        if context:
            augmented_message = f"Context:\n{context}\n\nQuestion: {user_message}"
        else:
            augmented_message = user_message

        messages = (
            [{"role": "system", "content": SYSTEM_PROMPT}]
            + self.history
            + [{"role": "user", "content": augmented_message}]
        )

        stream = self.client.chat(model=self.model, messages=messages, stream=True)

        full_response = ""
        for chunk in stream:
            text = chunk.message.content
            full_response += text
            yield text

        # Store clean messages so history stays stable across turns
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": full_response})

    def reset(self) -> None:
        """Clear conversation history."""
        self.history = []
