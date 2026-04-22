from collections.abc import Generator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

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

Base the suggestions strictly on the "Related sections" provided in the message — they are document chunks semantically similar to the question. Each suggestion should be a natural question a user could ask about one of those related sections."""


class RAGChatbot:
    """Multi-turn chatbot that grounds responses in retrieved document context."""

    def __init__(self, vector_store: VectorStore, model: str = "llama3.2"):
        self._model = model
        self._llm = ChatOllama(model=model)
        self.vector_store = vector_store
        self._db = ChatHistory()
        self.history: list[dict] = self._db.load()

    @property
    def model(self) -> str:
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        self._model = value
        self._llm = ChatOllama(model=value)

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
        response = self._llm.invoke([HumanMessage(content=prompt)])
        return response.content.strip()

    def _retrieve_context(self, query: str, n_results: int = 3) -> tuple[str, str]:
        """Return (answer_context, suggestion_context).

        Fetches 2×n_results chunks: top-n for answering, next-n as suggestion seeds.
        """
        docs = self.vector_store.similarity_search(query, k=n_results * 2)
        if not docs:
            return "", ""
        answer_docs = docs[:n_results]
        suggest_docs = docs[n_results:]
        answer_ctx = "\n\n".join(f"[Document {i + 1}]\n{doc}" for i, doc in enumerate(answer_docs))
        suggest_ctx = "\n\n".join(f"[Related {i + 1}]\n{doc}" for i, doc in enumerate(suggest_docs))
        return answer_ctx, suggest_ctx

    def _build_messages(self, augmented_message: str) -> list:
        """Convert stored history dicts + new message into LangChain message objects."""
        messages = [SystemMessage(content=SYSTEM_PROMPT)]
        for m in self.history:
            if m["role"] == "user":
                messages.append(HumanMessage(content=m["content"]))
            elif m["role"] == "assistant":
                messages.append(AIMessage(content=m["content"]))
        messages.append(HumanMessage(content=augmented_message))
        return messages

    def stream(self, user_message: str) -> Generator[str, None, None]:
        """Yield response tokens. Caller must call commit() after exhausting this generator."""
        self._db.append("user", user_message)

        retrieval_query = self._rewrite_query(user_message)
        context, related = self._retrieve_context(retrieval_query)

        if context and related:
            augmented_message = (
                f"Context:\n{context}\n\n"
                f"Related sections (base follow-up suggestions on these):\n{related}\n\n"
                f"Question: {user_message}"
            )
        elif context:
            augmented_message = f"Context:\n{context}\n\nQuestion: {user_message}"
        else:
            augmented_message = user_message

        for chunk in self._llm.stream(self._build_messages(augmented_message)):
            yield chunk.content

    def commit(self, user_message: str, assistant_response: str) -> None:
        """Persist a completed exchange to memory and the database."""
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": assistant_response})
        self._db.append("assistant", assistant_response)

    def reset(self) -> None:
        """Clear conversation history from memory and the database."""
        self.history = []
        self._db.clear()
