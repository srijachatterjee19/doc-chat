# DocChat

A RAG (Retrieval-Augmented Generation) chatbot that answers questions about your documents.

**Stack:** Ollama · LangChain · ChromaDB · FastAPI · React/Vite · Razorpay

---

## Prerequisites

- [Ollama](https://ollama.com) running locally
- Python 3.11+
- Node.js 18+

Pull the required models:

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
```

---

## Setup

**Python dependencies:**

```bash
pip install -r requirements.txt
```

**Frontend dependencies:**

```bash
cd frontend && npm install
```

**Environment variables:**

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `RAZORPAY_KEY_ID` | Payments | Razorpay key ID (`rzp_test_...`) |
| `RAZORPAY_KEY_SECRET` | Payments | Razorpay key secret |
| `LANGCHAIN_API_KEY` | Optional | LangSmith tracing |
| `VITE_GA_MEASUREMENT_ID` | Optional | Google Analytics 4 (in `frontend/.env`) |

---

## Ingest documents

Supported formats: `.txt`, `.md`, `.pdf`

```bash
# ingest one or more files
python -m backend.ingest data/sample.txt
python -m backend.ingest file1.txt file2.pdf

# clear all stored chunks
python -m backend.ingest --clear

# clear then re-ingest
python -m backend.ingest --clear data/sample.txt

# custom chunk size and overlap
python -m backend.ingest --chunk-size 400 --overlap 50 paper.pdf
```

Documents are split into overlapping word-count chunks, embedded with `nomic-embed-text` via LangChain, and stored in `./chroma_db`. Files already in the store are skipped automatically (matched by filename).

| Flag | Default | Description |
|------|---------|-------------|
| `--chunk-size` | `200` | Words per chunk |
| `--overlap` | `20` | Words shared between consecutive chunks |
| `--clear` | — | Wipe all chunks before ingesting |

---

## Run

**Terminal 1 — API server:**

```bash
uvicorn backend.api:app --reload
```

**Terminal 2 — React dev server:**

```bash
cd frontend && npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

The Vite dev server proxies all `/api/*` requests to the FastAPI backend at `localhost:8000`.

### Production (single server)

```bash
cd frontend && npm run build
uvicorn backend.api:app
```

FastAPI serves the built React app from `frontend/dist/` at [http://localhost:8000](http://localhost:8000).

---

## CLI (no UI)

```bash
python -m backend.chatbot
```

Commands: `reset` to clear history, `quit` to exit.

---

## Project structure

```
rag-chatbot/
├── backend/
│   ├── api.py            # FastAPI server (streaming SSE, /api/* routes)
│   ├── chatbot.py        # Interactive CLI
│   ├── ingest.py         # Document ingestion script
│   ├── app.py            # Legacy Streamlit UI
│   └── src/
│       ├── history.py     # JSON file-backed chat history
│       ├── rag.py         # RAGChatbot — retrieval + streaming chat
│       ├── vector_store.py # LangChain Chroma wrapper
│       └── embeddings.py  # Ollama embedding model wrapper
├── frontend/             # React + Vite UI
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── App.css
│   │   └── components/
│   │       ├── Sidebar.jsx
│   │       ├── ChatHeader.jsx
│   │       ├── MessageList.jsx
│   │       ├── InputArea.jsx
│   │       ├── LoginPage.jsx
│   │       ├── SignupPage.jsx
│   │       └── PricingPage.jsx
│   ├── vite.config.js
│   └── package.json
├── data/
│   └── sample.txt        # Sample knowledge base
└── requirements.txt
```

---

## How it works

1. **Ingest** — documents are chunked and embedded with `nomic-embed-text`; vectors are stored in ChromaDB
2. **Query rewriting** — vague follow-up questions are rewritten into standalone search queries using recent conversation history
3. **Retrieval** — the rewritten query is used to find the top-k most relevant chunks via cosine similarity
4. **Augmentation** — retrieved chunks are injected into the prompt as context
5. **Generation** — the LLM streams a response grounded in the retrieved context
6. **Suggestions** — follow-up questions are grounded in semantically similar chunks from the vector store (see below)

---

## Design decisions

### LangChain as the orchestration layer

The app uses [LangChain](https://python.langchain.com) (`ChatOllama`, `OllamaEmbeddings`, `langchain-chroma`) rather than calling Ollama and ChromaDB directly.

**Why:** LangChain provides a consistent interface across LLM providers and vector stores, making it straightforward to swap models or backends. It also integrates directly with LangSmith for tracing — every chain step (embedding, retrieval, generation) is automatically instrumented without any extra code.

**Trade-off:** Adds a layer of abstraction and dependency weight. For a simple single-provider setup, raw SDK calls would be leaner. The abstraction pays off here because of the observability and potential to swap components.

---

### Backend request tracking

Every HTTP request is logged to stdout as a newline-delimited JSON event, capturing method, path, status code, client IP, latency, and a short `request_id` that is also returned in the `X-Request-ID` and `X-Duration-Ms` response headers.

Chat completions emit a second `chat` event after the stream closes with deeper metrics:

| Field | Description |
|-------|-------------|
| `model` | Ollama model used |
| `message_chars` | Character length of the user message |
| `response_chars` | Character length of the full assistant response |
| `first_token_ms` | Time from request to first streamed token — reflects retrieval + queue latency |
| `total_stream_ms` | Total generation time for the full response |

Document uploads emit an `upload` event with `filename`, `file_bytes`, and the updated `doc_count`.

Example log lines:

```json
{"time": "2026-04-22T10:01:23", "level": "INFO", "message": "POST /api/chat", "request_id": "a3f9c1d2", "method": "POST", "path": "/api/chat", "status_code": 200, "duration_ms": 42.1, "client_ip": "127.0.0.1"}
{"time": "2026-04-22T10:01:31", "level": "INFO", "message": "chat completed", "event": "chat", "model": "llama3.2", "message_chars": 38, "response_chars": 512, "first_token_ms": 310.4, "total_stream_ms": 8201.7}
```

Because the format is newline-delimited JSON, logs can be piped directly into any aggregator (Datadog, CloudWatch, etc.) without a parsing step.

**Viewing logs**

Logs print to stdout in the same terminal where you run `uvicorn`. To save them to a file and watch live:

```bash
uvicorn api:app --reload 2>&1 | tee api.log
```

In a second terminal, filter to only the JSON events and pretty-print them:

```bash
tail -f api.log | grep '^{' | python3 -m json.tool
```

`grep '^{'` strips out uvicorn's plain-text lines so only your structured events come through.

---

### LangSmith for observability

Each request is traced end-to-end in [LangSmith](https://smith.langchain.com) with zero code instrumentation — just three environment variables in `.env`:

```
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_key_here
LANGCHAIN_PROJECT=rag-chatbot
```

**What gets traced:** the query rewrite LLM call, the vector store similarity search (with query, results, and latency), and the final streaming generation. Each turn shows token counts, latency per step, and the full prompt sent to the model.

**Why this matters:** without tracing it's hard to tell whether a bad answer is caused by poor retrieval (wrong chunks) or poor generation (good chunks, weak answer). LangSmith lets you inspect each step independently.

---

### In-process caching

Two caches reduce repeated Ollama round-trips within a server session.

**Embedding cache** (`src/embeddings.py`)

`embed_single` is backed by a module-level `lru_cache(maxsize=512)` keyed on `(model, text)`. Embedding is deterministic — the same string always produces the same vector — so the result is stored after the first call and returned instantly on any repeat. This matters because the query rewriter can produce the same standalone query for multiple slightly different phrasings, and the same query text is embedded twice (once for rewriting, once for retrieval).

**Similarity search cache** (`src/vector_store.py`)

`similarity_search` uses an `OrderedDict`-backed LRU cache (`maxsize=128`) keyed on `(query, k)`. A cache hit skips both the embedding call and the ChromaDB nearest-neighbor scan. The cache is cleared on `add_texts` and `delete_all` so results never go stale after documents change.

**What these don't cover**

The LLM calls themselves — the query rewrite and the final streaming response — are not cached. Each message still incurs at least one LLM call before retrieval begins.

---

### Similarity-grounded follow-up suggestions

After answering, the app suggests follow-up questions the user might ask. Rather than letting the LLM invent suggestions from scratch (which produces generic or hallucinated questions), suggestions are grounded in the vector store.

**How it works:**

- Retrieval fetches `2 × n` chunks instead of `n`
- The top `n` chunks are used as context for answering
- The next `n` chunks — semantically close to the query but not the closest — represent adjacent topics in the document
- Those adjacent chunks are passed to the LLM as `Related sections`, and the system prompt instructs it to derive suggestions from them

**Why this is better than free-form generation:** every suggestion maps to content that actually exists in the document. If the user clicks a suggestion and asks the question, retrieval will find relevant context because the suggestion was seeded from a real chunk.

---

## Testing query rewriting

The sample document (`data/sample.txt`) covers AI/ML topics. Use this conversation sequence to verify that follow-up questions retrieve the right context even when phrased vaguely:

| Turn | Message | What it tests |
|------|---------|---------------|
| 1 | `What are the three types of machine learning?` | Baseline retrieval |
| 2 | `Can you give me an example of each?` | Vague follow-up — rewriter expands "each" using turn 1 |
| 3 | `Which one is used in recommendation systems?` | Pronoun-heavy — rewriter infers "one" = ML type |
| 4 | `What about the visual side of AI?` | Topic shift |
| 5 | `What are some real-world applications of that?` | "that" has no standalone meaning without history |

Without query rewriting, turns 2, 3, and 5 would search ChromaDB with phrases like "give me an example of each" and pull wrong chunks. With rewriting, each question is reformulated into a standalone query before retrieval.

---

## API reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/status` | Number of ingested document chunks |
| `GET` | `/api/models` | Available Ollama chat models |
| `GET` | `/api/history` | Full conversation history |
| `POST` | `/api/chat` | Stream a chat response (SSE) |
| `POST` | `/api/reset` | Clear conversation history |
| `POST` | `/api/upload` | Upload and ingest a document (`.txt`, `.md`, `.pdf`, max 10 MB) |
| `POST` | `/api/history/rollback` | Remove an orphaned user turn with no assistant reply |
| `POST` | `/api/payments/create-order` | Create a Razorpay order for the Pro plan |
| `POST` | `/api/payments/verify` | Verify Razorpay payment signature and return tier |

Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Payments & plans

DocChat uses [Razorpay](https://razorpay.com) for payments (UPI, cards, netbanking, wallets).

| Plan | Price | Limits |
|------|-------|--------|
| Free | ₹0/mo | 10 messages/day · 2 documents |
| Pro | ₹799/mo | Unlimited messages · Unlimited documents |

### Razorpay setup

1. Sign up at [dashboard.razorpay.com](https://dashboard.razorpay.com)
2. Go to **Settings → API Keys** → generate a key pair
3. Add `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` to `.env`

Use `rzp_test_...` keys during development — no real money is charged.

### User flow

1. User clicks **Upgrade to Pro** in the `•••` menu
2. Backend creates a Razorpay order and returns the order ID
3. Razorpay checkout modal opens in the browser
4. User pays → frontend calls `/api/payments/verify` to confirm the signature
5. On success, `pro` is stored in `localStorage`
