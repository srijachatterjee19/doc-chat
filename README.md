# RAG Chatbot

A local RAG (Retrieval-Augmented Generation) chatbot that answers questions about your documents. Fully local — no API keys required.

**Stack:** Ollama · ChromaDB · FastAPI · React/Vite

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

```bash
python ingest.py data/sample.txt
# or multiple files
python ingest.py path/to/file1.txt path/to/file2.txt
```

Documents are chunked into 200-word overlapping segments, embedded with `nomic-embed-text`, and stored in a persistent ChromaDB database (`./chroma_db`).

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
├── app.py            # Streamlit UI (alternative to React frontend)
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
│   ├── embeddings.py  # Ollama embedding wrapper
│   ├── rag.py         # RAGChatbot — retrieval + streaming chat
│   └── vector_store.py # ChromaDB wrapper
└── data/
    └── sample.txt     # Sample knowledge base
```

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
| `POST` | `/api/chat` | Stream a chat response (SSE) |
| `POST` | `/api/reset` | Clear conversation history |

Interactive docs available at [http://localhost:8000/docs](http://localhost:8000/docs) when the server is running.
