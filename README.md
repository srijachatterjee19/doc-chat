# RAG Chatbot

A local RAG (Retrieval-Augmented Generation) chatbot that answers questions about your documents. Fully local — no API keys required.

**Stack:** Ollama · LangChain · ChromaDB · FastAPI · React/Vite

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

---

## Ingest documents

Supported formats: `.txt`, `.md`, `.pdf`

```bash
# ingest one or more files
python ingest.py data/sample.txt
python ingest.py file1.txt file2.pdf

# clear all stored chunks
python ingest.py --clear

# clear then re-ingest
python ingest.py --clear data/sample.txt

# custom chunk size and overlap
python ingest.py --chunk-size 400 --overlap 50 paper.pdf
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
uvicorn api:app --reload
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
uvicorn api:app
```

FastAPI serves the built React app from `frontend/dist/` at [http://localhost:8000](http://localhost:8000).

---

## CLI (no UI)

```bash
python chatbot.py
```

Commands: `reset` to clear history, `quit` to exit.

---

## Project structure

```
rag-chatbot/
├── api.py            # FastAPI backend (streaming SSE, /api/* routes)
├── chatbot.py        # Interactive CLI
├── ingest.py         # Document ingestion script
├── requirements.txt
├── frontend/         # React + Vite UI
│   ├── src/
│   │   ├── App.jsx
│   │   └── App.css
│   ├── vite.config.js
│   └── package.json
├── src/
│   ├── history.py     # SQLite-backed chat history
│   ├── rag.py         # RAGChatbot — retrieval + streaming chat (ChatOllama)
│   └── vector_store.py # LangChain Chroma wrapper (embeddings handled internally)
└── data/
    └── sample.txt     # Sample knowledge base
```

---

## How it works

1. **Ingest** — documents are chunked and embedded with `nomic-embed-text`; vectors are stored in ChromaDB
2. **Query rewriting** — vague follow-up questions are rewritten into standalone search queries using recent conversation history
3. **Retrieval** — the rewritten query is used to find the top-k most relevant chunks via cosine similarity
4. **Augmentation** — retrieved chunks are injected into the prompt as context
5. **Generation** — the LLM streams a response grounded in the retrieved context

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

Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)
