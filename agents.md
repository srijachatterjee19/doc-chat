# Agents

This app uses a three-agent CrewAI pipeline to generate responses. Agents run sequentially via `Process.sequential`. All agents use `gpt-4o-mini` with a 1500-token output limit.

**File:** `backend/src/rag.py` → `_run_crew()`

---

## Agent 1 — Document Analyst

| Property | Value |
|---|---|
| Role | Document Analyst |
| Goal | Find and summarize relevant information from the user's uploaded documents |
| Runs when | Documents are loaded and the query is about them, or context is sufficient |
| Allow delegation | No |

### Tool: Search Documents

A custom CrewAI tool that wraps the app's own vector store. When called, it runs a cosine similarity search against ChromaDB (`k=5`) and returns the top matching chunks labelled by index.

```
Input:  query (str)
Output: "[Chunk 1]\n<text>\n\n[Chunk 2]\n<text>..."
        or "No relevant content found in the uploaded documents."
```

The agent is explicitly instructed to call this tool multiple times with different query terms to ensure thorough coverage. It is also told never to fabricate — only report what the documents actually contain.

---

## Agent 2 — Web Researcher

| Property | Value |
|---|---|
| Role | Web Researcher |
| Goal | Find up-to-date information from the web |
| Runs when | No documents are loaded, or retrieved context is insufficient to answer the question |
| Allow delegation | No |

### Tool: SerperDevTool

A built-in CrewAI tool (`crewai_tools.SerperDevTool`) that wraps the Serper API — a Google Search API. The agent is told to find 2–3 reliable sources and include a URL for every fact it reports.

**Requires:** `SERPER_API_KEY` in your `.env` file. If the key is missing, the Web Researcher will fail and the crew will fall back to whatever the Document Analyst found (or the single-LLM fallback path).

---

## Agent 3 — Synthesizer

| Property | Value |
|---|---|
| Role | Synthesizer |
| Goal | Produce a single well-structured answer that clearly attributes each piece of information |
| Runs when | Always — receives outputs from whichever agents ran before it |
| Allow delegation | No |
| Tools | None |

The Synthesizer has no tools. It only sees the outputs of the preceding agents as context and writes the final response in a fixed format:

```
📄 From your documents:
<what the documents say>

🌐 From Google Search:
<web findings with inline source URLs>

**Summary:**
<1-2 sentence answer>

**You might also ask:**
- <follow-up 1>
- <follow-up 2>
- <follow-up 3>
```

Sections are included or excluded depending on which agents ran (e.g. if only the Document Analyst ran, the Google Search section is omitted).

---

## Routing — Which Agents Run

The routing decision is made in `stream()` before the crew starts, based on what was retrieved from the vector store and what the message is about:

| Condition | Agents used |
|---|---|
| No docs loaded, not asking about documents | Web Researcher + Synthesizer |
| Asking about uploaded docs, or context is sufficient | Document Analyst + Synthesizer |
| Context found but insufficient for the question | Document Analyst + Web Researcher + Synthesizer |

---

## Status Updates

As each agent starts and finishes, a status event is pushed to the frontend in real time:

```json
{ "type": "agent_update", "agent": "Document Analyst", "icon": "📄", "summary": "Searching your documents…", "status": "working" }
{ "type": "agent_update", "agent": "Document Analyst", "icon": "📄", "summary": "<truncated output>", "status": "done" }
```

Statuses: `pending` → `working` → `done`. The frontend renders these as a live progress panel above the response.

---

## Fallback

If CrewAI is unavailable (import error) or the crew returns an empty/whitespace response, the pipeline falls back to a direct `gpt-4o-mini` call using LangChain's `ChatOpenAI`, with the retrieved context prepended to the question. No agent panels are shown in this case.

---

## Semantic Similarity

Cosine similarity over OpenAI `text-embedding-3-small` embeddings is used in two distinct ways before the agents even run:

### 1. History Relevance Check
**File:** `backend/src/rag.py` → `_history_is_relevant()`

The current message and the last 4 history messages are embedded and compared using a hand-rolled `_cosine()` function (in-memory, no DB involved). If similarity is below **0.65**, conversation history is excluded from the current query — preventing unrelated follow-up questions from being polluted by prior conversation context.

### 2. Document Retrieval
**File:** `backend/src/vector_store.py` → `similarity_search_with_sources()`

The query is embedded and compared against all stored chunk embeddings inside ChromaDB using cosine similarity (`hnsw:space: cosine`). This is the core of the RAG pipeline — it determines which document chunks the Document Analyst receives as context.

### Why two separate implementations?

| | History check | Document retrieval |
|---|---|---|
| Implementation | `_cosine()` — pure Python, in-memory | ChromaDB HNSW index |
| Input | Two embedding vectors | Query vector vs. entire chunk collection |
| Purpose | Decide whether to include history | Find the most relevant document chunks |

The same underlying concept (cosine similarity over the same embedding model) is used in both places, but ChromaDB handles its own indexing and search internally — the hand-rolled `_cosine()` only exists for the lightweight in-memory history comparison.
