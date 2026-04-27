# Application Flow

This document describes the full lifecycle of a user message, from the moment it is sent to the moment a response is rendered.

---

## Message Lifecycle

### 1. Profanity Check
**File:** `backend/api.py` → `_contains_profanity()`

The message is checked against a frozenset of blocked terms using regex word-boundary matching. If a match is found, a rejection message is returned immediately and the pipeline stops.

---

### 2. Cache Lookup
**File:** `backend/src/rag.py` → `_get_cached()`

The cache key is:
```
normalized_message | doc_fingerprint
```
where `doc_fingerprint` is a sorted, comma-joined list of all ingested filenames. If there is a cache hit, the stored response is streamed back immediately — no LLM calls are made. The cache holds up to 128 entries (LRU eviction).

---

### 3. History Relevance Check
**File:** `backend/src/rag.py` → `_history_is_relevant()`

The current message and the last 4 history messages are embedded using OpenAI `text-embedding-3-small`. Cosine similarity is computed between them. If similarity is below **0.65**, the conversation history is treated as irrelevant to the current question and excluded from the context window.

---

### 4. Query Rewriting
**File:** `backend/src/rag.py` → `_rewrite_query()`

Only runs if history is relevant. Sends the recent conversation (last 6 turns) and the current question to `gpt-4o-mini`, asking it to produce a concise standalone search query that captures the full intent. This rewritten query is used for vector store retrieval — not the raw user message.

---

### 5. Context Retrieval
**File:** `backend/src/rag.py` → `_retrieve_context()`

Two paths:

- **Filename mentioned in query:** If the message contains the name of an ingested file, all chunks for that file are fetched directly from ChromaDB (ordered by chunk index), bypassing semantic search.
- **Semantic search (default):** Runs a cosine similarity search over the ChromaDB vector store (top 6 results). The top 3 become the answer context; the bottom 3 become the "related sections" used to generate follow-up suggestions.

All retrieved chunks are labelled with their source filename.

---

### 6. Routing Decision
**File:** `backend/src/rag.py` → `stream()`

Based on what was retrieved and what the message is asking about:

| Condition | Agents used |
|---|---|
| No context found, not asking about docs | Web Researcher + Synthesizer |
| Asking about uploaded docs, or context is sufficient | Document Analyst + Synthesizer |
| Context found but insufficient for the question | Document Analyst + Web Researcher + Synthesizer |

"Asking about uploaded docs" is detected by matching against a set of trigger phrases (`summarize`, `what's in`, `my document`, etc.) or by detecting an ingested filename in the message.

"Context is sufficient" is a YES/NO call to `gpt-4o-mini` that checks whether the retrieved chunks can fully answer the question.

---

### 7. CrewAI Agents
**File:** `backend/src/rag.py` → `_run_crew()`

Agents run sequentially via CrewAI. Status updates (`agent_update` events) are pushed to the frontend in real time as each agent starts and finishes.

**Document Analyst**
- Tool: searches the vector store using `similarity_search()` with multiple queries
- Reports what the uploaded documents contain, or states clearly if nothing relevant was found

**Web Researcher** *(only when context is insufficient or no docs are loaded)*
- Tool: Serper (Google Search API)
- Finds 2–3 reliable sources and includes URLs for every finding

**Synthesizer**
- Combines outputs from the above agents
- Formats the final response with clearly labelled sections (`📄 From your documents`, `🌐 From Google Search`)
- Appends 3 follow-up question suggestions

All agents use `gpt-4o-mini`.

---

### 8. Response Streaming
**File:** `backend/api.py` → `generate()`

The final response is split into 20-word chunks and sent as Server-Sent Events (`text/event-stream`). The frontend appends each chunk to the message as it arrives.

Once the full response has been received, `commit()` is called, which:
- Appends the user message and assistant response to the in-memory history
- Persists both to the SQLite chat history database
- Stores the response in the LRU cache

---

## Data Flow Diagram

```
User message
     │
     ▼
Profanity check ──── blocked ──► rejection message
     │
     ▼
Cache lookup ──── hit ──────────► stream cached response
     │ miss
     ▼
History relevance check (cosine similarity ≥ 0.65?)
     │
     ▼
Query rewriting (if history relevant)
     │
     ▼
ChromaDB retrieval
  ├── filename mentioned → fetch all chunks for that file
  └── default → semantic similarity search (top 6 chunks)
     │
     ▼
Routing: doc only / web only / doc + web
     │
     ▼
CrewAI agents (sequential)
  ├── Document Analyst (vector store search)
  ├── Web Researcher (Serper/Google)
  └── Synthesizer (combines + formats)
     │
     ▼
SSE stream to frontend
     │
     ▼
commit() → history + DB + cache
```

---

## Key Files

| File | Role |
|---|---|
| `backend/api.py` | FastAPI routes, SSE streaming, profanity guard, upload/delete |
| `backend/src/rag.py` | Full RAG pipeline: cache, retrieval, routing, CrewAI orchestration |
| `backend/src/vector_store.py` | ChromaDB wrapper: add, search, delete, list sources |
| `backend/src/embeddings.py` | OpenAI `text-embedding-3-small` wrapper with LRU cache |
| `backend/src/history.py` | SQLite persistence for conversation history |
| `backend/ingest.py` | Document ingestion: PDF/TXT/MD parsing and chunking |
| `frontend/src/App.jsx` | Main React app: SSE consumer, state management |
| `frontend/src/components/` | UI components: Sidebar, MessageList, InputArea, ChatHeader |
