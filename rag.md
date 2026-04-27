# How RAG Works in This App

RAG (Retrieval-Augmented Generation) grounds LLM responses in your actual documents rather than the model's training data. The LLM never sees your raw documents — it only sees the chunks that are relevant to the current question.

---

## Ingestion (one-time setup)

**File:** `backend/ingest.py`

When a document is uploaded, it goes through three steps:

1. **Parse** — text is extracted from `.txt`, `.md`, or `.pdf` files
2. **Chunk** — text is split using LangChain's `RecursiveCharacterTextSplitter`:
   - Default: **1000 characters per chunk**, **200-character overlap**
   - Splits on paragraph breaks (`\n\n`) → line breaks (`\n`) → sentences (`. `) → words, in that order — so chunks always break at the most natural boundary available
   - Overlap preserves context across chunk boundaries so a sentence split across two chunks isn't lost
3. **Embed + store** — each chunk is embedded using OpenAI `text-embedding-3-small` and stored in ChromaDB with metadata:
   - `source` — the original filename
   - `chunk` — the chunk index (used to reconstruct document order)

Files already in the store (matched by filename) are skipped automatically.

```
Document
   │
   ▼
Parse text (PDF/TXT/MD)
   │
   ▼
RecursiveCharacterTextSplitter
(paragraph → line → sentence → word boundaries)
1000 chars per chunk, 200-char overlap
   │
   ▼
Embed each chunk (text-embedding-3-small)
   │
   ▼
Store in ChromaDB with {source, chunk} metadata
```

---

## Retrieval (every query)

**File:** `backend/src/rag.py` → `_retrieve_context()`

Two retrieval paths depending on the query:

### Path A — Filename mentioned
If the user's message contains the name of an ingested file (e.g. "summarise report.pdf"), all chunks for that file are fetched directly from ChromaDB and ordered by chunk index. No similarity search is needed because the user is explicitly asking about a specific document.

### Path B — Semantic search (default)
The query (rewritten if conversation history is relevant) is embedded and compared against all stored chunk embeddings using cosine similarity. The top 6 most similar chunks are returned:
- **Top 3** → answer context (sent to the Document Analyst agent)
- **Bottom 3** → related sections (used to generate follow-up question suggestions)

All retrieved chunks are labelled with their source filename and chunk number, e.g.:
```
[report.pdf — chunk 3]
The quarterly revenue increased by 12%...
```

---

## Augmentation

The retrieved chunks are prepended to the question before any LLM call. The Document Analyst agent also runs multiple searches with different query terms to improve coverage — it is explicitly instructed never to fabricate information beyond what the documents contain.

The prompt structure sent to the LLM looks like:

```
Available documents: report.pdf, notes.txt

[report.pdf — chunk 1]
<text>

[report.pdf — chunk 3]
<text>

Question: What was the revenue growth?
```

---

## Generation

The Synthesizer agent receives the Document Analyst's findings (and web results if needed) and writes a structured response attributed to its sources. The system prompt instructs it to:
- Only use information from the provided context
- Label each section by source (`📄 From your documents` / `🌐 From Google Search`)
- Append 3 follow-up question suggestions based on the related sections

---

## Vector Store

**File:** `backend/src/vector_store.py`

Backed by **ChromaDB** with cosine similarity as the distance metric (`hnsw:space: cosine`). Key operations:

| Method | Purpose |
|---|---|
| `add_texts()` | Embed and insert chunks |
| `similarity_search_with_sources()` | Top-k semantic search, returns (text, filename) pairs |
| `get_all_chunks_for_source()` | Fetch all chunks for a file, ordered by index |
| `delete_source()` | Remove all chunks for a given file |
| `list_sources()` | Return all ingested files with chunk counts |

Search results are cached with an LRU cache (128 entries) to avoid re-embedding identical queries.

---

## Embeddings

**File:** `backend/src/embeddings.py`

All embeddings — both at ingestion time and query time — use **OpenAI `text-embedding-3-small`**. Individual embedding calls are cached with `@lru_cache` (512 entries) so repeated queries don't incur extra API costs.

The same embedding model is used for both documents and queries, which is required for cosine similarity to be meaningful.

---

## Chunking Trade-offs

The current defaults (1000 chars, 200-char overlap) are a reasonable starting point. Tuning these affects retrieval quality:

| Setting | Smaller value | Larger value |
|---|---|---|
| `chunk_size` | More precise retrieval, may miss broader context | Captures more context per chunk, but noisier similarity scores |
| `overlap` | Risk of losing cross-boundary context | Better continuity, more redundant storage |

To re-ingest with different settings:
```bash
.venv-crewai/bin/python -m backend.ingest --clear --chunk-size 1500 --overlap 300 data/yourfile.pdf
```

---

## Performance Optimisations

### Query Rewriting Threshold
**File:** `backend/src/rag.py` → `_rewrite_query()`

Query rewriting sends the conversation history to `gpt-4o-mini` to produce a better standalone search query. This only fires when there are **at least 4 messages in history (2 full turns)** — with fewer exchanges there isn't enough context to meaningfully improve the query, so the original message is used as-is, saving an LLM call.

### Sufficiency Check Cache
**File:** `backend/src/rag.py` → `_context_is_sufficient()`

The sufficiency check makes a `gpt-4o-mini` call to decide whether the retrieved context is enough to answer the question. Results are cached using an MD5 hash of `(question, context)` as the key (up to 256 entries, LRU eviction). If the same question retrieves the same chunks again, the YES/NO decision is returned from cache with no LLM call.

### Response Cache
**File:** `backend/src/rag.py` → `_get_cached()` / `_set_cached()`

Exact repeated questions skip the entire pipeline. The cache key is `normalized_message | doc_fingerprint` where `doc_fingerprint` is the sorted list of ingested filenames — so the cache is automatically invalidated when documents are added or removed. Holds up to 128 entries (LRU eviction).

**Important:** the cache is in-memory only. It is cleared whenever the server restarts. When running with `uvicorn --reload`, any file save triggers a restart and wipes the cache — so to verify caching is working, send both messages without touching any files in between.

Cache hits and misses are logged to the terminal:
```
cache hit:  "what is ai"
cache miss: "what is ai"
```

**Edge case fixed:** if the crew returns a whitespace-only response, `_stream_text` produces no chunks and `full_response` stays empty, so `commit()` would never be called and nothing would be cached. The crew response is now stripped before the truthiness check to prevent this.

### Vector Search Cache
**File:** `backend/src/vector_store.py` → `similarity_search_with_sources()`

ChromaDB similarity search results are cached by `(query, k)` — up to 128 entries. Cache is cleared whenever new documents are added or deleted.
