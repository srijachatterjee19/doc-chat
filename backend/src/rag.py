import contextvars
import hashlib
import logging
import math
import queue
import threading
from collections import OrderedDict
from collections.abc import Generator

logger = logging.getLogger("rag")

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .embeddings import EmbeddingModel
from .history import ChatHistory
from .vector_store import VectorStore

_embedder = EmbeddingModel()


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(x * x for x in b))
    return dot / norm if norm else 0.0

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

_CHUNK_SIZE = 20


def _stream_text(text: str) -> Generator[dict, None, None]:
    """Yield text in word-chunks as SSE-compatible dicts."""
    words = text.split()
    for i in range(0, len(words), _CHUNK_SIZE):
        yield {"type": "text", "text": " ".join(words[i : i + _CHUNK_SIZE]) + " "}


def _humanize_summary(text: str, max_chars: int = 120) -> str:
    """Truncate raw agent output to a short human-readable summary."""
    text = text.strip().replace("\n", " ")
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"


class RAGChatbot:
    """Multi-turn chatbot that grounds responses in retrieved document context."""

    _CACHE_MAX = 128

    def __init__(self, vector_store: VectorStore, model: str = "gpt-4o-mini", history_path=None):
        self._model = model
        self._llm = ChatOpenAI(model=model)
        self.vector_store = vector_store
        self._db = ChatHistory(path=history_path) if history_path else ChatHistory()
        self.history: list[dict] = self._db.load()
        self._response_cache: OrderedDict[str, str] = OrderedDict()
        self._sufficiency_cache: OrderedDict[str, bool] = OrderedDict()

    def _cache_key(self, message: str) -> str:
        doc_fingerprint = ",".join(sorted(s["name"] for s in self.vector_store.list_sources()))
        return f"{message.strip().lower()}|{doc_fingerprint}"

    def _get_cached(self, message: str) -> str | None:
        key = self._cache_key(message)
        if key in self._response_cache:
            self._response_cache.move_to_end(key)
            return self._response_cache[key]
        return None

    def _set_cached(self, message: str, response: str) -> None:
        key = self._cache_key(message)
        self._response_cache[key] = response
        self._response_cache.move_to_end(key)
        if len(self._response_cache) > self._CACHE_MAX:
            self._response_cache.popitem(last=False)

    @property
    def model(self) -> str:
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        self._model = value
        self._llm = ChatOpenAI(model=value)

    def _rewrite_query(self, user_message: str) -> str:
        if len(self.history) < 4:  # need at least 2 prior turns to rewrite meaningfully
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
        sources = self.vector_store.list_sources()
        source_list = ", ".join(s["name"] for s in sources) if sources else "none"
        header = f"Available documents: {source_list}\n\n"

        # If a specific ingested filename is mentioned, fetch all its chunks directly
        query_lower = query.lower()
        mentioned = next(
            (s["name"] for s in sources if s["name"].lower() in query_lower), None
        )
        if mentioned:
            chunks = self.vector_store.get_all_chunks_for_source(mentioned)
            if chunks:
                answer_ctx = header + "\n\n".join(
                    f"[{mentioned} — chunk {i + 1}]\n{c}" for i, c in enumerate(chunks[:12])
                )
                return answer_ctx, ""

        # Default: semantic similarity search
        docs = self.vector_store.similarity_search_with_sources(query, k=n_results * 2)
        if not docs:
            return "", ""
        answer_docs = docs[:n_results]
        suggest_docs = docs[n_results:]
        answer_ctx = header + "\n\n".join(
            f"[{src} — chunk {i + 1}]\n{text}" for i, (text, src) in enumerate(answer_docs)
        )
        suggest_ctx = "\n\n".join(
            f"[{src} — related {i + 1}]\n{text}" for i, (text, src) in enumerate(suggest_docs)
        )
        return answer_ctx, suggest_ctx

    def _history_is_relevant(self, current_message: str, threshold: float = 0.65) -> bool:
        """Return True if the current message is semantically related to recent history."""
        if not self.history:
            return False
        recent = " ".join(m["content"] for m in self.history[-4:])
        try:
            sim = _cosine(
                _embedder.embed_single(current_message),
                _embedder.embed_single(recent),
            )
            return sim >= threshold
        except Exception:
            return True  # fail open — include history if embedding fails

    def _build_messages(self, augmented_message: str, use_history: bool = True) -> list:
        messages = [SystemMessage(content=SYSTEM_PROMPT)]
        if use_history:
            for m in self.history[:-1]:  # exclude the pending user turn
                if m["role"] == "user":
                    messages.append(HumanMessage(content=m["content"]))
                elif m["role"] == "assistant":
                    messages.append(AIMessage(content=m["content"]))
        messages.append(HumanMessage(content=augmented_message))
        return messages

    def _context_is_sufficient(self, question: str, context: str) -> bool:
        """Quick YES/NO check: can the retrieved context answer the question?"""
        if not context:
            return False
        key = hashlib.md5(f"{question.strip().lower()}|{context}".encode()).hexdigest()
        if key in self._sufficiency_cache:
            return self._sufficiency_cache[key]
        response = self._llm.invoke([
            SystemMessage(content="You decide if provided context can answer a question. Reply only YES or NO."),
            HumanMessage(content=f"Context:\n{context}\n\nQuestion: {question}"),
        ])
        result = "yes" in response.content.strip().lower()
        self._sufficiency_cache[key] = result
        if len(self._sufficiency_cache) > 256:
            self._sufficiency_cache.popitem(last=False)
        return result

    def _make_doc_search_tool(self):
        """Return a CrewAI tool that queries the chatbot's own vector store."""
        from crewai.tools import tool
        vector_store = self.vector_store

        @tool("Search Documents")
        def search_documents(query: str) -> str:
            """Search the user's uploaded documents for information relevant to the query.
            Use this tool with different search terms to find all relevant content."""
            docs = vector_store.similarity_search(query, k=5)
            if not docs:
                return "No relevant content found in the uploaded documents."
            return "\n\n".join(f"[Chunk {i + 1}]\n{doc}" for i, doc in enumerate(docs))

        return search_documents

    def _run_crew(self, query: str, update_queue: queue.Queue, use_doc: bool = True, use_web: bool = True) -> str:
        """Run CrewAI agents and push live status updates into update_queue.

        Routing:
          use_doc=True,  use_web=False → doc analyst + synthesizer only
          use_doc=True,  use_web=True  → all 3 agents
          use_doc=False, use_web=True  → web researcher + synthesizer only
        Falls back to empty string if crewai is unavailable.
        """
        try:
            from crewai import Agent, Crew, LLM, Process, Task
            from crewai_tools import SerperDevTool
        except ImportError:
            return ""

        llm = LLM(model="gpt-4o-mini", max_tokens=1500)

        # Emit initial states for whichever agents will run
        if use_doc:
            update_queue.put({"type": "agent_update", "agent": "Document Analyst", "icon": "📄", "summary": "Searching your documents…", "status": "working"})
        if use_web:
            status = "pending" if use_doc else "working"
            summary = "Standing by…" if use_doc else "Searching the web…"
            update_queue.put({"type": "agent_update", "agent": "Web Researcher", "icon": "🌐", "summary": summary, "status": status})
        update_queue.put({"type": "agent_update", "agent": "Synthesizer", "icon": "🔀", "summary": "Waiting for results…", "status": "pending"})

        def on_doc_done(output):
            summary = _humanize_summary(output.raw) if output.raw else "Finished searching documents."
            update_queue.put({"type": "agent_update", "agent": "Document Analyst", "icon": "📄", "summary": summary, "status": "done"})
            if use_web:
                update_queue.put({"type": "agent_update", "agent": "Web Researcher", "icon": "🌐", "summary": "Searching the web…", "status": "working"})
            else:
                update_queue.put({"type": "agent_update", "agent": "Synthesizer", "icon": "🔀", "summary": "Summarising…", "status": "working"})

        def on_web_done(output):
            summary = _humanize_summary(output.raw) if output.raw else "Web search complete."
            update_queue.put({"type": "agent_update", "agent": "Web Researcher", "icon": "🌐", "summary": summary, "status": "done"})
            update_queue.put({"type": "agent_update", "agent": "Synthesizer", "icon": "🔀", "summary": "Combining results…", "status": "working"})

        def on_synth_done(_output):
            update_queue.put({"type": "agent_update", "agent": "Synthesizer", "icon": "🔀", "summary": "Response ready.", "status": "done"})

        synth_agent = Agent(
            role="Synthesizer",
            goal="Produce a single well-structured answer that clearly attributes each piece of information",
            backstory="Expert at combining research from multiple sources into a coherent, attributed answer.",
            verbose=False, allow_delegation=False, llm=llm,
        )

        agents = []
        context_tasks = []

        if use_doc:
            doc_agent = Agent(
                role="Document Analyst",
                goal="Find and summarize relevant information from the user's uploaded documents",
                backstory=(
                    "Expert at querying document collections and extracting key information. "
                    "You always use the search tool with multiple relevant queries to ensure thorough coverage. "
                    "You never fabricate — only report what the documents actually contain."
                ),
                verbose=False, allow_delegation=False, llm=llm,
                tools=[self._make_doc_search_tool()],
            )
            doc_task = Task(
                description=(
                    f"Use the Search Documents tool to find all relevant information about: {query}\n\n"
                    "Search using multiple relevant terms and phrases to ensure thorough coverage. "
                    "Summarize what you find. If the documents contain nothing relevant, say so clearly."
                ),
                agent=doc_agent,
                callback=on_doc_done,
                expected_output="A concise summary of what the documents say, or that they don't cover the topic.",
            )
            agents.append(doc_agent)
            context_tasks.append(doc_task)

        if use_web:
            web_agent = Agent(
                role="Web Researcher",
                goal="Find up-to-date information from the web",
                backstory="Expert at searching the web and noting source URLs for every fact reported.",
                verbose=False, allow_delegation=False, llm=llm,
                tools=[SerperDevTool()],
            )
            web_task = Task(
                description=(
                    f"Search the web for current information about: {query}\n"
                    "Find 2-3 reliable sources. Include the source URL for each finding."
                ),
                agent=web_agent,
                callback=on_web_done,
                expected_output="A summary of web findings with source URLs.",
            )
            agents.append(web_agent)
            context_tasks.append(web_task)

        # Build synth prompt based on which sections exist
        sections = []
        if use_doc:
            sections.append("📄 **From your documents:**\n<what the documents say>")
        if use_web:
            sections.append("🌐 **From Google Search:**\n<web findings with inline source URLs>")
        sections.append("**Summary:**\n<1-2 sentence answer>")
        sections.append("**You might also ask:**\n- <follow-up 1>\n- <follow-up 2>\n- <follow-up 3>")

        synth_task = Task(
            description=(
                f"Write a complete answer to: {query}\n\n"
                "Format your response exactly like this:\n\n" + "\n\n".join(sections)
            ),
            agent=synth_agent,
            context=context_tasks,
            callback=on_synth_done,
            expected_output="A structured response with clearly labelled source sections.",
        )

        agents.append(synth_agent)
        crew = Crew(agents=agents, tasks=context_tasks + [synth_task], process=Process.sequential, verbose=False)
        result = crew.kickoff(inputs={"query": query})
        return result.raw

    _DOC_PHRASES = frozenset({
        "my doc", "my document", "my file", "my upload", "the document", "the file",
        "summarize", "summarise", "summarise", "what's in", "what is in",
        "tell me about", "overview of", "contents of",
    })

    def _is_about_uploaded_docs(self, message: str) -> bool:
        """Return True if the message is asking about the user's own uploaded documents."""
        msg = message.lower()
        if any(phrase in msg for phrase in self._DOC_PHRASES):
            return True
        ingested = {s["name"].lower() for s in self.vector_store.list_sources()}
        return any(name in msg for name in ingested)

    def stream(self, user_message: str, rewrite_query: bool = True) -> Generator:
        """Yield agent_update dicts then text dicts. Caller must call commit() after."""
        cached = self._get_cached(user_message)
        if cached:
            logger.info("cache hit: %r", user_message[:60])
            yield from _stream_text(cached)
            return
        logger.info("cache miss: %r", user_message[:60])

        use_history = self._history_is_relevant(user_message)
        retrieval_query = (
            self._rewrite_query(user_message)
            if (rewrite_query and use_history)
            else user_message
        )
        context, related = self._retrieve_context(retrieval_query)
        about_docs = self._is_about_uploaded_docs(user_message)

        if not context:
            # Nothing retrieved — web search only (unless they're asking about their docs,
            # in which case the doc agent will explain nothing was found)
            use_doc, use_web = (True, False) if about_docs else (False, True)
        elif about_docs or self._context_is_sufficient(user_message, context):
            use_doc, use_web = True, False
        else:
            use_doc, use_web = True, True

        update_queue: queue.Queue = queue.Queue()
        result_holder: list = [None, None]  # [response, error]

        def run_crew():
            try:
                result_holder[0] = self._run_crew(retrieval_query, update_queue, use_doc=use_doc, use_web=use_web)
            except Exception as e:
                result_holder[1] = e
            finally:
                update_queue.put(None)  # sentinel

        ctx = contextvars.copy_context()
        t = threading.Thread(target=ctx.run, args=(run_crew,), daemon=True)
        t.start()

        # Yield agent updates in real-time as crew works
        while True:
            item = update_queue.get()
            if item is None:
                break
            yield item

        t.join()

        crew_response = (result_holder[0] or "").strip()
        if crew_response:
            yield from _stream_text(crew_response)
            return

        # Fallback: original single-LLM path (if crewai unavailable)
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

        for chunk in self._llm.stream(self._build_messages(augmented_message, use_history=use_history)):
            yield chunk.content

    def commit(self, user_message: str, assistant_response: str) -> None:
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": assistant_response})
        self._db.append("user", user_message)
        self._db.append("assistant", assistant_response)
        self._set_cached(user_message, assistant_response)

    def reset(self) -> None:
        self.history = []
        self._db.clear()
        self._response_cache.clear()
        self._sufficiency_cache.clear()
