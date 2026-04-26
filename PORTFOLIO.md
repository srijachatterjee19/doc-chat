# DocChat — AI Portfolio Case Study

> A full-stack AI chatbot that combines document retrieval, multi-agent reasoning, real-time web search, and voice input into a single streaming interface.

---

## Overview

DocChat is a production-ready RAG (Retrieval-Augmented Generation) chatbot that answers questions about uploaded documents. When the documents don't have a complete answer, the system automatically falls back to real-time web search — and clearly tells the user which information came from where.

The project covers the full stack: a React frontend with live streaming UI, a FastAPI backend with Server-Sent Events, a ChromaDB vector store, a multi-agent CrewAI pipeline, and an OpenAI Whisper voice input system.

**Live stack:**

- **Frontend:** React 18 + Vite, Server-Sent Events, WebSocket
- **Backend:** FastAPI, Python 3.11
- **LLMs:** Ollama (local, for routing/rewriting) + GPT-4o-mini (CrewAI agents)
- **Vector DB:** ChromaDB with `nomic-embed-text` embeddings
- **Agents:** CrewAI with custom tools
- **Voice:** OpenAI Whisper via WebSocket streaming
- **Search:** Serper (Google Search API)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Frontend                           │
│  Voice input (WebSocket) ──▶ Input field ──▶ POST /api/chat     │
│                                                                 │
│  SSE stream ──▶ Agent status cards ──▶ Streaming response       │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP / WebSocket
┌─────────────────────────▼───────────────────────────────────────┐
│                      FastAPI Backend                            │
│                                                                 │
│  POST /api/chat ──▶ RAGChatbot.stream()                         │
│  WS   /ws/transcribe ──▶ Whisper transcription                  │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                    RAGChatbot (rag.py)                          │
│                                                                 │
│  1. Rewrite query    (Ollama)                                   │
│  2. Retrieve chunks  (ChromaDB)                                 │
│  3. Route            (Ollama — YES/NO sufficiency check)        │
│  4. Run crew         (CrewAI — background thread + queue)       │
│  5. Stream response  (SSE — agent cards + text chunks)          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Features

### 1. Intelligent Routing

Before running any agents, the system checks whether the retrieved document chunks are sufficient to answer the question. This keeps costs low and responses fast — Google Search is only called when it actually adds value.

```
No docs retrieved      →  Web Researcher + Synthesizer
Docs sufficient        →  Document Analyst + Synthesizer
Docs insufficient      →  Document Analyst + Web Researcher + Synthesizer
```

The routing decision is made with a single non-streaming Ollama call: _"Can this context answer this question? YES or NO."_

---

### 2. Multi-Agent Pipeline (CrewAI)

Three specialised agents run sequentially, each with a defined role and tool:

| Agent               | Tool                           | Responsibility                                       |
| ------------------- | ------------------------------ | ---------------------------------------------------- |
| 📄 Document Analyst | Custom `search_documents` tool | Queries the vector store, reports what documents say |
| 🌐 Web Researcher   | SerperDevTool (Google Search)  | Finds current web sources with URLs                  |
| 🔀 Synthesizer      | None (reasoning only)          | Combines both into a structured, attributed response |

**Why a custom document tool instead of pre-retrieved chunks?**

The Document Analyst is given an active `search_documents` tool that wraps `VectorStore.similarity_search()` rather than receiving pre-fetched chunks as static text. This means the agent can reformulate its own search queries and call the tool multiple times — important for multi-facet questions that a single retrieval pass would miss.

```python
@tool("Search Documents")
def search_documents(query: str) -> str:
    """Search the user's uploaded documents for information relevant to the query."""
    docs = vector_store.similarity_search(query, k=5)
    ...
```

---

### 3. Live Agent Status Streaming

The CrewAI crew runs in a **background thread** while the main generator streams agent status updates to the frontend in real time via Server-Sent Events.

```
SSE generator (main thread)        CrewAI crew (background thread)
       │                                      │
       │  ◀── agent_update (doc working) ─────┤
       │  ◀── agent_update (doc done) ────────┤
       │  ◀── agent_update (web working) ─────┤
       │  ◀── agent_update (web done) ─────────┤
       │  ◀── agent_update (synth done) ───────┤
       │  ◀── None (sentinel) ─────────────────┤
       │
       │  yield text chunks...
```

Each task fires a `callback` on completion that pushes a status dict into a `queue.Queue`. The main thread drains this queue live. The user sees exactly which agent is working and a humanised summary of what it found — before the final response streams in.

The SSE stream carries two event types:

| type           | payload                          | frontend action           |
| -------------- | -------------------------------- | ------------------------- |
| `agent_update` | `{agent, icon, summary, status}` | Update agent status card  |
| _(none)_       | `{text}`                         | Append to response bubble |

---

### 4. Query Rewriting

Vague follow-up questions are rewritten into self-contained search queries before hitting the vector store. Without this, queries like _"what about the visual side?"_ or _"give me an example"_ would retrieve irrelevant chunks.

The rewriter uses the last 6 turns of conversation history and the local Ollama model — fast and free.

| Turn | Raw message                                   | Rewritten query                                                      |
| ---- | --------------------------------------------- | -------------------------------------------------------------------- |
| 2    | _"Can you give me an example of each?"_       | _"examples of supervised, unsupervised, and reinforcement learning"_ |
| 3    | _"Which one is used in recommendations?"_     | _"machine learning type used in recommendation systems"_             |
| 5    | _"What are real-world applications of that?"_ | _"real-world applications of computer vision"_                       |

---

### 5. Voice Input with Whisper Streaming

Voice input uses `MediaRecorder` in the browser to stream audio chunks to the backend via WebSocket, where OpenAI Whisper transcribes the growing buffer in real time.

```
Browser mic → MediaRecorder (3s chunks) → WebSocket → backend buffer
                                                              │
                                                   Whisper transcribes
                                                   full buffer on each chunk
                                                              │
                                                   ◀── {text: "..."} ──
                                                              │
                                                   Input field updates live
```

**Why transcribe the full accumulated buffer each time?**

Whisper performs significantly better with more audio context. Transcribing only the latest chunk in isolation produces fragmented, error-prone output. By sending the full buffer on each update, the transcript becomes more accurate as the user continues speaking — earlier words get corrected as context grows.

When the user stops recording, `recorder.onstop` closes the WebSocket (after `ondataavailable` fires with the final chunk), ensuring the last audio is always processed.

---

### 6. Response Attribution

Every response clearly marks where information came from:

```
📄 From your documents:
   The document states that agentic AI is proactive and can autonomously...

🌐 From Google Search:
   Generative AI focuses on content creation while agentic AI automates
   workflows independently (IBM, [source](https://ibm.com/...))

Summary:
   Generative AI reacts to prompts; agentic AI acts autonomously to achieve goals.

You might also ask:
   - How do agentic AI systems handle unexpected situations?
   - ...
```

The Synthesizer's prompt template is generated dynamically based on which agents ran — if only web search was used, no document section appears, and vice versa.

---

### 7. Fallback Path

If the CrewAI package is unavailable, `stream()` automatically falls back to a direct Ollama call with the retrieved chunks injected as plain context. No code changes needed — the API surface is identical.

---

## Technical Decisions

### Why two LLMs?

| Model                | Used for                                      | Why                                                     |
| -------------------- | --------------------------------------------- | ------------------------------------------------------- |
| Ollama (local)       | Query rewriting, routing, fallback generation | Free, fast, no API latency, runs on device              |
| GPT-4o-mini (OpenAI) | CrewAI agents                                 | Reliable tool-use — local models hallucinate tool calls |

Local models consistently fail to follow the ReAct tool-calling format required by CrewAI. Using GPT-4o-mini only for the agent layer keeps the tool calls reliable while keeping costs minimal (mini is cheap).

### Why SSE instead of WebSockets for chat?

SSE is one-directional (server → client) and simpler to implement for streaming text. The chat request is a standard HTTP POST; only the response needs to stream. WebSockets add bidirectional complexity that isn't needed here. The voice transcription endpoint is the one place that genuinely needs bidirectionality, and that uses WebSockets correctly.

### Why a background thread for CrewAI?

CrewAI's `crew.kickoff()` is synchronous and blocking. FastAPI's streaming response (`StreamingResponse`) expects a generator that yields values. Running the crew in a background thread with a `queue.Queue` lets the generator yield agent status updates in real time as the crew works, rather than waiting for the entire crew to finish before returning anything.

### Why pre-retrieve chunks if the Document Analyst has its own search tool?

The pre-retrieved chunks are used only for the **routing decision** (is context sufficient?). The Document Analyst then queries the vector store independently with its own search terms. This separates two concerns: the routing check needs a quick representative sample, while the agent needs freedom to search comprehensively.

---

## Project Structure

```
rag-chatbot/
├── backend/
│   ├── api.py              # FastAPI — SSE chat, WebSocket transcription, file upload
│   ├── ingest.py           # Document chunking + embedding pipeline
│   └── src/
│       ├── rag.py          # RAGChatbot — all AI logic (routing, agents, streaming)
│       ├── vector_store.py # ChromaDB wrapper with LRU similarity search cache
│       ├── embeddings.py   # Ollama embedding model with LRU cache
│       ├── history.py      # JSON-backed multi-turn conversation history
│       └── analytics.py    # PostgreSQL event logging (DAU, retention, funnel)
├── frontend/
│   └── src/
│       ├── App.jsx         # Chat state, SSE handler, agent update routing
│       └── components/
│           ├── MessageList.jsx   # Agent status cards + markdown-rendered responses
│           ├── InputArea.jsx     # Voice recording (MediaRecorder + WebSocket)
│           └── ...
├── data/
└── requirements.txt
```

---

---

## Frontend Deep Dive

The frontend is a React 18 + Vite SPA. The core challenge was building a UI that handles real-time streaming from two different protocols (SSE for chat, WebSocket for voice), renders live agent status cards as they arrive, and stays responsive throughout.

---

### Component map

```
App.jsx  ──────────────────────────────────────────────────────
│  owns all state: messages, streaming, agentUpdates, theme
│
├── Sidebar.jsx           document list + file upload
├── ChatHeader.jsx        doc count, theme toggle, dropdown menu
├── MessageList.jsx       renders messages + live agent cards
└── InputArea.jsx         text input + voice recording + send
```

---

### App.jsx — state and SSE handler

`App.jsx` is the single source of truth for all chat state. The most important piece is the SSE handler inside `sendMessage()`.

**State managed:**

| State          | Type                               | Purpose                                                         |
| -------------- | ---------------------------------- | --------------------------------------------------------------- |
| `messages`     | `{role, content}[]`                | Full conversation history rendered in the UI                    |
| `streaming`    | `boolean`                          | Disables input and send button while response is in flight      |
| `agentUpdates` | `{agent, icon, summary, status}[]` | Live agent status cards shown above the streaming response      |
| `documents`    | array                              | Sidebar document list                                           |
| `theme`        | `'dark' \| 'light'`                | Persisted to `localStorage`, applied via `data-theme` attribute |

**The SSE streaming loop:**

```js
const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = "";

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  const lines = buffer.split("\n");
  buffer = lines.pop() ?? ""; // keep incomplete line for next chunk

  for (const line of lines) {
    if (!line.startsWith("data: ")) continue;
    const parsed = JSON.parse(line.slice(6));

    if (parsed.type === "agent_update") {
      // upsert into agentUpdates by agent name
    } else if (parsed.text) {
      // append to last message's content
    }
  }
}
```

**Why `response.body.getReader()` instead of `EventSource`?**

The native `EventSource` API only supports `GET` requests. The chat endpoint needs to be a `POST` (to send the message body). Using `ReadableStream` with a manual SSE parser gives the same streaming behaviour without that constraint.

**Why a buffer?**

The `TextDecoder` can split a UTF-8 character or an SSE line across two `read()` calls. The buffer accumulates raw bytes and only processes complete lines (split on `\n`), with the last incomplete line held over for the next iteration.

**Agent update upsert:**

Agent cards are stored by agent name. When the same agent transitions from `working` to `done`, `findIndex` locates the existing card and replaces it in place — so cards don't flash or reorder, they update smoothly.

```js
setAgentUpdates((prev) => {
  const idx = prev.findIndex((u) => u.agent === parsed.agent);
  if (idx >= 0) {
    const next = [...prev];
    next[idx] = parsed;
    return next;
  }
  return [...prev, parsed];
});
```

---

### MessageList.jsx — markdown rendering and agent cards

**Two responsibilities:**

1. Render each message (user = plain text, assistant = ReactMarkdown)
2. Show live agent status cards above the last assistant message

**Why ReactMarkdown only for assistant messages?**

User messages are plain text and need `white-space: pre-wrap` to preserve line breaks. Assistant messages come from the LLM and contain markdown (bold headers, bullet lists, links). Applying ReactMarkdown to user messages would incorrectly parse things like asterisks in normal speech.

**Agent cards placement:**

```jsx
{
  messages.map((msg, i) => {
    const isLastAssistant =
      msg.role === "assistant" && i === messages.length - 1;
    return (
      <div key={i}>
        {isLastAssistant && agentUpdates.length > 0 && (
          <div className="agent-activity">
            {agentUpdates.map((u) => (
              <AgentCard key={u.agent} {...u} />
            ))}
          </div>
        )}
        <div className={`message ${msg.role}`}>...</div>
      </div>
    );
  });
}
```

Cards only appear above the last assistant message — not on historical turns. When the response is complete, they stay visible so the user can see which sources were used.

**Three card states:**

| Status    | Visual             | Meaning                       |
| --------- | ------------------ | ----------------------------- |
| `pending` | Grey dot, dimmed   | Agent queued, not started     |
| `working` | Orange pulsing dot | Agent currently running       |
| `done`    | Green dot          | Agent finished, summary shown |

**Auto-scroll:**

`useEffect` triggers `scrollIntoView({ behavior: 'smooth' })` on both `messages` and `agentUpdates` dependency changes — so the view follows as agent cards appear and the response streams in.

---

### InputArea.jsx — voice input with WebSocket streaming

The mic button uses the browser's `MediaRecorder` API to capture audio and streams it to the backend via WebSocket in real time.

**Recording flow:**

```
getUserMedia()              →  request mic permission
new WebSocket('/ws/...')    →  open connection to backend
new MediaRecorder(stream)   →  set up recorder with detected mimeType
recorder.start(3000)        →  send a chunk every 3 seconds
recorder.ondataavailable    →  ws.send(e.data) on each chunk
ws.onmessage                →  onInputChange(text) — update input live
recorder.onstop             →  ws.close() — close AFTER last chunk is sent
```

**Why `recorder.onstop` closes the socket, not `stopRecording()`?**

`MediaRecorder.stop()` is asynchronous. It fires `ondataavailable` with the final chunk, then fires `onstop`. If you close the WebSocket in `stopRecording()` directly, the final chunk may be sent after the socket is already closed and gets dropped. Closing in `onstop` guarantees the last chunk has been sent.

**Why transcribe the full buffer each time?**

Whisper is a sequence model — more audio context produces more accurate transcription. Transcribing only the latest 3-second chunk in isolation produces fragmented results. The backend accumulates all received audio and transcribes the full buffer on each chunk, so accuracy improves as the user continues speaking.

**Mime type detection:**

Different browsers support different audio formats. Rather than hard-coding `audio/webm`, the component probes for support in order of preference:

```js
const types = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/mp4",
  "audio/ogg",
];
return types.find((t) => MediaRecorder.isTypeSupported(t)) ?? "";
```

---

### ChatHeader.jsx — click-outside dropdown

The header contains a `•••` dropdown menu (Upgrade, Clear, Sign out). A common interview question is how to close a dropdown when clicking outside it.

```js
useEffect(() => {
  function handleClick(e) {
    if (!menuRef.current?.contains(e.target)) setMenuOpen(false);
  }
  document.addEventListener("mousedown", handleClick);
  return () => document.removeEventListener("mousedown", handleClick);
}, []);
```

`Node.contains()` checks if the click target is inside the menu element. If it isn't, the menu closes. The listener is added to `document` (not the menu itself) so it catches clicks anywhere on the page. The cleanup function in the `useEffect` return removes the listener when the component unmounts, preventing memory leaks.

---

### Sidebar.jsx — document management

The sidebar lists ingested documents and handles file uploads. Two behaviours based on file type:

- **PDF** — clicking opens the file in a new browser tab (`/api/files/{name}`)
- **Text/Markdown** — clicking pre-fills the input with _"What is {filename} about?"_

File upload uses `FormData` and a hidden `<input type="file">` triggered via a ref, allowing a styled button rather than the browser's default file picker.

---

### Theme system

The entire colour palette is defined as CSS custom properties on `:root` (dark) and `[data-theme="light"]` (light). Toggling theme is a single attribute change on `<html>`:

```js
document.documentElement.setAttribute("data-theme", theme);
```

This means no class toggling, no JavaScript colour calculations — every component automatically picks up the right colours because they all reference variables like `var(--bg)`, `var(--text)`, `var(--accent)`.

The preference is persisted to `localStorage` and read on first render, so the theme survives page refresh.

---

### Protected routes and auth

```jsx
function ProtectedRoute({ children }) {
  return isLoggedIn() ? children : <Navigate to="/login" replace />;
}
```

`isLoggedIn()` checks for a `loggedIn` key in `localStorage`. This is intentionally simple — the project uses client-side auth as a UI gate (not a security boundary). In a production system this would be replaced with JWT verification or a session cookie check.

---

### Analytics

Every significant user action fires a tracking event through `analytics.js`:

```js
track("first_message", { model: selectedModel });
track("upload_document", { file_type: file.type });
track("model_change", { model });
```

`track()` sends to both Google Analytics 4 and the backend `/api/metrics/event` endpoint (which logs to PostgreSQL). The user is identified by a UUID generated once and stored in `localStorage`. This lets you correlate frontend events with backend logs using the same user ID.

---

## AI Agent Deep Dive

The AI logic lives almost entirely in `backend/src/rag.py`. `RAGChatbot.stream()` is the single entry point — it orchestrates five steps and yields a mixed stream of agent status events and text chunks.

---

### Full pipeline flow

```
stream(user_message)
    │
    ├─ 1. _rewrite_query()          Ollama — standalone search query from conversation context
    │
    ├─ 2. _retrieve_context()       ChromaDB — top-6 chunks split into answer pool + suggest pool
    │
    ├─ 3. _context_is_sufficient()  Ollama YES/NO — is the answer pool enough?
    │
    ├─ 4. routing decision
    │       no docs         →  use_doc=False, use_web=True
    │       docs sufficient →  use_doc=True,  use_web=False
    │       docs partial    →  use_doc=True,  use_web=True
    │
    ├─ 5. _run_crew()               CrewAI in background thread → yields agent_update dicts
    │
    └─ 6. yield text chunks         _stream_text() → yields {"type":"text","text":"..."} dicts
```

---

### Step 1 — Query rewriting

Multi-turn conversations produce vague follow-up questions that retrieve nothing useful from the vector store: _"what about the visual side?"_, _"give me an example"_. The rewriter converts these into self-contained search queries.

```python
def _rewrite_query(self, user_message: str) -> str:
    if not self.history:
        return user_message          # first message needs no rewriting
    history_text = "\n".join(
        f"{m['role'].capitalize()}: {m['content']}" for m in self.history[-6:]
    )
    prompt = (
        f"Conversation so far:\n{history_text}\n\n"
        f"Rewrite the following question as a concise standalone search query...\n\n"
        f"Question: {user_message}\nStandalone query:"
    )
    response = self._llm.invoke([HumanMessage(content=prompt)])
    return response.content.strip()
```

**Why last 6 turns only?** Context window cost. Six turns (3 exchanges) is enough to resolve pronouns and follow-up references without sending the entire history to Ollama on every keystroke. The first message short-circuits entirely — nothing to resolve.

---

### Step 2 — Context retrieval

```python
def _retrieve_context(self, query: str, n_results: int = 3) -> tuple[str, str]:
    docs = self.vector_store.similarity_search(query, k=n_results * 2)   # fetch 6
    answer_docs  = docs[:n_results]    # top 3 → used for answering
    suggest_docs = docs[n_results:]    # next 3 → used for follow-up suggestions
    answer_ctx  = "\n\n".join(f"[Document {i+1}]\n{doc}" ...)
    suggest_ctx = "\n\n".join(f"[Related  {i+1}]\n{doc}" ...)
    return answer_ctx, suggest_ctx
```

**Split retrieval pool:** The top 3 chunks go to the answer context; the next 3 go to a separate suggestions pool. The LLM uses the suggestions pool _only_ to generate the "You might also ask" follow-ups — this avoids polluting the answer context with lower-relevance chunks while still giving the model material to suggest useful next questions.

---

### Step 3 — Context sufficiency check

```python
def _context_is_sufficient(self, question: str, context: str) -> bool:
    if not context:
        return False
    response = self._llm.invoke([
        SystemMessage(content="You decide if provided context can answer a question. Reply only YES or NO."),
        HumanMessage(content=f"Context:\n{context}\n\nQuestion: {question}"),
    ])
    return "yes" in response.content.strip().lower()
```

**Why a whole LLM call just for YES/NO?** A keyword search or length check can't determine semantic sufficiency. A document might contain many words about the topic but still not answer the specific question. The Ollama call is non-streaming and typically returns in under a second, making it cheap enough to run on every query.

The `.lower()` + `"yes" in` approach is intentionally loose — models sometimes return _"Yes, the context..."_ rather than a bare _"YES"_.

---

### Step 4 — Routing

```python
if not context:
    use_doc, use_web = False, True      # docs empty → web only
elif self._context_is_sufficient(user_message, context):
    use_doc, use_web = True, False      # docs enough → skip web
else:
    use_doc, use_web = True, True       # docs partial → both
```

This routing is the reason the system avoids unnecessary API calls: Google Search (via Serper) and GPT-4o-mini both cost money. The YES/NO check gates them behind a relevance decision.

---

### Step 5 — CrewAI agents

#### Agent definitions

Each agent is given a minimal, focused role. The key configuration choices:

```python
doc_agent = Agent(
    role="Document Analyst",
    goal="Find and summarize relevant information from the user's uploaded documents",
    backstory=(
        "Expert at querying document collections... "
        "You always use the search tool with multiple relevant queries to ensure thorough coverage. "
        "You never fabricate — only report what the documents actually contain."
    ),
    verbose=False, allow_delegation=False, llm=llm,
    tools=[self._make_doc_search_tool()],
)
```

`allow_delegation=False` prevents agents from spinning up sub-agents, which would bypass the routing logic and unpredictably increase costs. Each agent has exactly one tool or none.

#### The custom document search tool

```python
def _make_doc_search_tool(self):
    from crewai.tools import tool
    vector_store = self.vector_store

    @tool("Search Documents")
    def search_documents(query: str) -> str:
        """Search the user's uploaded documents for information relevant to the query.
        Use this tool with different search terms to find all relevant content."""
        docs = vector_store.similarity_search(query, k=5)
        if not docs:
            return "No relevant content found in the uploaded documents."
        return "\n\n".join(f"[Chunk {i+1}]\n{doc}" for i, doc in enumerate(docs))

    return search_documents
```

**Why a tool instead of pre-fetched chunks?** Pre-fetching gives the agent static text. An active tool lets the Document Analyst issue multiple searches with different phrasings — important for multi-facet questions. For _"what are the benefits and risks of X?"_, a single retrieval pass might find the benefits section but miss the risks section. An active tool lets the agent search _"benefits of X"_ and _"risks of X"_ separately.

The closure captures `self.vector_store` so the tool has access to the live, up-to-date vector store without any global state.

#### Task callbacks and live status

```python
def on_doc_done(output):
    summary = _humanize_summary(output.raw) if output.raw else "Finished searching documents."
    update_queue.put({"type": "agent_update", "agent": "Document Analyst", ..., "status": "done"})
    if use_web:
        update_queue.put({"type": "agent_update", "agent": "Web Researcher", ..., "status": "working"})
    else:
        update_queue.put({"type": "agent_update", "agent": "Synthesizer", ..., "status": "working"})
```

Each CrewAI `Task` accepts a `callback` that fires when that task completes. The callback is the bridge between the CrewAI sequential process and the real-time status stream — it pushes a status dict into `queue.Queue` the moment the task finishes, regardless of what the main thread is doing.

**`_humanize_summary()`** truncates the raw agent output to 120 characters for display in the status card:

```python
def _humanize_summary(text: str, max_chars: int = 120) -> str:
    text = text.strip().replace("\n", " ")
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"
```

It uses `rsplit(" ", 1)[0]` to avoid cutting in the middle of a word.

#### Dynamic synthesizer prompt

The Synthesizer's output format is built at runtime based on which agents ran:

```python
sections = []
if use_doc:
    sections.append("📄 **From your documents:**\n<what the documents say>")
if use_web:
    sections.append("🌐 **From Google Search:**\n<web findings with inline source URLs>")
sections.append("**Summary:**\n<1-2 sentence answer>")
sections.append("**You might also ask:**\n- <follow-up 1>\n...")
```

If only web search ran, no document section appears in the output. If only documents ran, no web section appears. This keeps the response clean regardless of the routing decision.

---

### Step 6 — Background thread + queue pattern

This is the most architecturally interesting piece. CrewAI's `crew.kickoff()` is blocking — it doesn't return until all agents have finished. But FastAPI's `StreamingResponse` needs a generator that yields values continuously. Running the crew on the main thread would produce nothing until the entire crew completed.

**Solution: background thread + `queue.Queue`**

```python
update_queue: queue.Queue = queue.Queue()
result_holder: list = [None, None]   # [response, error]

def run_crew():
    try:
        result_holder[0] = self._run_crew(query, update_queue, ...)
    except Exception as e:
        result_holder[1] = e
    finally:
        update_queue.put(None)    # None = sentinel: crew is done

t = threading.Thread(target=run_crew, daemon=True)
t.start()

# Main thread drains the queue in real time
while True:
    item = update_queue.get()     # blocks until something is available
    if item is None:
        break
    yield item                    # SSE event to client

t.join()
crew_response = result_holder[0]
yield from _stream_text(crew_response)
```

```
Main thread (SSE generator)           Background thread (CrewAI)
         │                                       │
         │  get() ← blocks ────────────────────  │  put(agent_update: doc working)
         │  yield agent_update                   │
         │  get() ← blocks ────────────────────  │  put(agent_update: doc done)
         │  yield agent_update                   │
         │  get() ← blocks ────────────────────  │  put(None)  ← sentinel
         │  break loop                           │
         │                                       │
         │  join()  ← wait for thread to exit    │  (finishes)
         │  yield text chunks from result
```

`queue.Queue.get()` blocks until an item is available — this gives the main thread something to do (yield the item) the instant a callback fires, without polling. `daemon=True` means the thread is killed automatically if the process exits, preventing zombie threads.

---

### Fallback path

If CrewAI is not installed, `stream()` falls back to a direct Ollama call:

```python
crew_response = result_holder[0]
if crew_response:
    yield from _stream_text(crew_response)
    return

# Fallback: original single-LLM path
augmented_message = f"Context:\n{context}\n\nQuestion: {user_message}"
for chunk in self._llm.stream(self._build_messages(augmented_message)):
    yield chunk.content
```

The fallback yields raw strings (not dicts), which the `generate()` function in `api.py` handles separately via the `else` branch. The API contract to the frontend stays identical.

---

### Conversation history management

History is stored in two places:

| Store     | Class                      | Format              | Scope                                 |
| --------- | -------------------------- | ------------------- | ------------------------------------- |
| In-memory | `self.history`             | `[{role, content}]` | Loaded at startup, modified in-flight |
| On-disk   | `ChatHistory` (history.py) | JSON file           | Persisted across restarts             |

`commit()` writes to both after a complete response:

```python
def commit(self, user_message: str, assistant_response: str) -> None:
    self.history.append({"role": "user",      "content": user_message})
    self.history.append({"role": "assistant", "content": assistant_response})
    self._db.append("assistant", assistant_response)
```

Note that `_db.append("user", ...)` is called at the start of `stream()`, before generation begins. This means if the connection drops mid-stream, the user turn is already written. `history_rollback()` (`POST /api/history/rollback`) removes that orphaned user turn — it's called by the frontend's error handler if the SSE stream fails.

---

## Backend–Frontend Communication

The backend exposes three distinct communication channels, each chosen for a specific reason.

---

### Channel overview

| Channel             | Protocol   | Endpoint            | Direction                               | Used for                             |
| ------------------- | ---------- | ------------------- | --------------------------------------- | ------------------------------------ |
| Chat streaming      | HTTP + SSE | `POST /api/chat`    | Server → Client (after initial request) | LLM text chunks + agent status       |
| Voice transcription | WebSocket  | `WS /ws/transcribe` | Bidirectional binary/text               | Audio chunks in, transcript text out |
| Data API            | HTTP REST  | `/api/*`            | Request/response                        | History, models, upload, metrics     |

---

### 1. Server-Sent Events — chat streaming

**Why SSE instead of WebSocket here?**

The chat flow is naturally one-directional once the request is sent: the client POSTs a message and then only reads. SSE is simpler to implement, supported natively by browsers, and works over standard HTTP. WebSockets would add bidirectional complexity for no benefit. The one reason SSE is sometimes avoided — it only supports `GET` — is bypassed by consuming the `ReadableStream` manually from a `fetch()` call instead of using the `EventSource` API.

**Wire format**

FastAPI's `StreamingResponse` wraps every event in the SSE envelope:

```
data: {"type": "agent_update", "agent": "Document Analyst", "icon": "📄", "summary": "Searching your documents…", "status": "working"}\n\n
data: {"type": "agent_update", "agent": "Document Analyst", "icon": "📄", "summary": "Found 3 relevant chunks.", "status": "done"}\n\n
data: {"text": "The document explains that "}\n\n
data: {"text": "agentic AI systems are proactive… "}\n\n
data: [DONE]\n\n
```

Each message is `data: <JSON>\n\n`. The stream ends with the sentinel `data: [DONE]\n\n`.

**Two SSE event types**

| `type` field      | Payload fields                       | Frontend action                           |
| ----------------- | ------------------------------------ | ----------------------------------------- |
| `agent_update`    | `agent`, `icon`, `summary`, `status` | Upsert agent status card by agent name    |
| _(no type field)_ | `text`                               | Append string to last message's `content` |

The backend `generate()` function in `api.py` serialises both types:

```python
for chunk in _chatbot.stream(request.message, ...):
    if isinstance(chunk, dict):
        if chunk.get("type") == "agent_update":
            yield f"data: {json.dumps(chunk)}\n\n"
        elif chunk.get("type") == "text":
            full_response += chunk["text"]
            yield f"data: {json.dumps({'text': chunk['text']})}\n\n"
    else:
        # Ollama fallback — raw string
        full_response += chunk
        yield f"data: {json.dumps({'text': chunk})}\n\n"
yield "data: [DONE]\n\n"
```

**Frontend parsing**

The frontend reads the stream with `response.body.getReader()` and a manual line parser:

```js
const reader = response.body.getReader()
const decoder = new TextDecoder()
let buffer = ''

while (true) {
  const { done, value } = await reader.read()
  if (done) break
  buffer += decoder.decode(value, { stream: true })
  const lines = buffer.split('\n')
  buffer = lines.pop() ?? ''    // hold incomplete line for next chunk

  for (const line of lines) {
    if (!line.startsWith('data: ') || line === 'data: [DONE]') continue
    const parsed = JSON.parse(line.slice(6))

    if (parsed.type === 'agent_update') {
      setAgentUpdates(prev => /* upsert by agent name */)
    } else if (parsed.text) {
      setMessages(prev => /* append to last assistant message */)
    }
  }
}
```

The buffer is necessary because a single `read()` call can split a UTF-8 character or an SSE line boundary across two chunks. Incomplete lines are carried forward rather than parsed immediately.

---

### 2. WebSocket — voice transcription

**Why WebSocket here?**

Transcription is genuinely bidirectional: the browser sends binary audio chunks while simultaneously receiving text transcript updates. SSE can't send binary data, and standard HTTP would require waiting until recording finishes before sending anything. WebSocket is the natural fit.

**Wire format**

```
Client → Server:  raw binary audio (ArrayBuffer, webm/mp4/ogg)
Server → Client:  JSON text frame {"text": "Hello, world"}
```

**Backend handler (`api.py`)**

```python
@app.websocket("/ws/transcribe")
async def transcribe_ws(websocket: WebSocket):
    await websocket.accept()
    audio_buffer = bytearray()
    loop = asyncio.get_event_loop()

    try:
        async for chunk in websocket.iter_bytes():
            audio_buffer.extend(chunk)      # accumulate full audio
            transcript = await loop.run_in_executor(
                _transcribe_executor,
                _whisper_transcribe,
                bytes(audio_buffer),        # transcribe growing buffer
            )
            if transcript:
                await websocket.send_json({"text": transcript})
    except (WebSocketDisconnect, RuntimeError):
        pass
```

`run_in_executor` offloads the synchronous Whisper API call to a `ThreadPoolExecutor`, keeping the async event loop unblocked. Both `WebSocketDisconnect` and `RuntimeError` are caught — `RuntimeError` covers the race condition where the client closes before the first `iter_bytes` fires.

**Frontend flow**

```
getUserMedia()              →  browser mic permission
new WebSocket('/ws/...')    →  open connection
MediaRecorder.start(3000)   →  fire ondataavailable every 3 seconds
ondataavailable             →  ws.send(e.data) binary chunk
ws.onmessage                →  onInputChange(parsed.text) — populate input field
recorder.onstop             →  ws.close()  (AFTER last ondataavailable)
```

`ws.close()` lives in `recorder.onstop`, not in `stopRecording()`. This is a subtle timing issue: `MediaRecorder.stop()` is asynchronous — it fires `ondataavailable` with the final chunk _before_ it fires `onstop`. Closing the socket in `stopRecording()` directly can drop that final chunk.

---

### 3. REST endpoints

| Method | Path                     | Request                           | Response             | Purpose                         |
| ------ | ------------------------ | --------------------------------- | -------------------- | ------------------------------- |
| `POST` | `/api/chat`              | `{message, model, rewrite_query}` | SSE stream           | Chat with streaming response    |
| `GET`  | `/api/history`           | —                                 | `{messages: [...]}`  | Load conversation history       |
| `GET`  | `/api/models`            | —                                 | `{models: [...]}`    | Available Ollama models         |
| `GET`  | `/api/status`            | —                                 | `{doc_count: N}`     | Vector store chunk count        |
| `GET`  | `/api/documents`         | —                                 | `{documents: [...]}` | Ingested files + chunk counts   |
| `POST` | `/api/upload`            | `multipart/form-data` (file)      | `{ok, doc_count}`    | Ingest a document               |
| `GET`  | `/api/files/{filename}`  | —                                 | File bytes           | Serve uploaded file inline      |
| `POST` | `/api/reset`             | —                                 | `{ok: true}`         | Clear conversation history      |
| `POST` | `/api/history/rollback`  | —                                 | `{ok: true}`         | Remove orphaned last user turn  |
| `POST` | `/api/metrics/event`     | `{event, user_id, properties}`    | `{ok: true}`         | Log analytics event             |
| `GET`  | `/api/metrics/dau`       | `?days=30`                        | `{dau: [...]}`       | Daily active users              |
| `GET`  | `/api/metrics/retention` | `?days=30`                        | `{retention: [...]}` | Day-7 retention by cohort       |
| `GET`  | `/api/metrics/funnel`    | —                                 | `{funnel: [...]}`    | Conversion funnel data          |
| `WS`   | `/ws/transcribe`         | binary audio frames               | `{"text": "..."}`    | Real-time Whisper transcription |

**Request model for `/api/chat`**

```python
class ChatRequest(BaseModel):
    message: str
    model: str = "llama3.2"
    rewrite_query: bool = True
```

---

### 4. CORS and the Vite proxy

In development, the React dev server runs on port `5173` while FastAPI runs on `8000`. Two approaches are used together:

**FastAPI CORS middleware** allows the dev origin directly:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Vite proxy** routes `/api` and `/ws` through the dev server so the browser sees requests going to the same origin — avoiding preflight issues:

```js
// vite.config.js
server: {
  proxy: {
    '/api': { target: 'http://localhost:8000', changeOrigin: true },
    '/ws':  { target: 'ws://localhost:8000',  ws: true },
  }
}
```

The `ws: true` flag is required for WebSocket proxying — Vite won't upgrade the connection without it.

In production, the React build is served as static files from FastAPI itself (`app.mount("/", StaticFiles(...))`), so there is no cross-origin issue and no proxy.

---

### 5. Request tracking middleware

Every HTTP response carries two headers added by a custom middleware:

```python
@app.middleware("http")
async def track_requests(request: Request, call_next):
    request_id = uuid4().hex[:8]
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 1)

    logger.info("%s %s", request.method, request.url.path, extra={
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
    })
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Duration-Ms"] = str(duration_ms)
    return response
```

`X-Request-ID` lets you correlate a specific frontend request with a backend log line. `X-Duration-Ms` exposes server-side latency to the browser's network tab. All log output is structured JSON (via a custom `_JsonFormatter`) so logs are machine-parseable without regex.

---

## What I Learned

- **Multi-agent orchestration is a routing problem first.** The hardest part wasn't building the agents — it was deciding when to use them. A bad routing decision either wastes API calls or gives incomplete answers.

- **LLM tool-use reliability varies wildly by model size.** Sub-7B local models hallucinate tool names instead of using the ones provided. This made it necessary to use an API model specifically for the agent layer, while keeping local models for cheaper tasks.

- **Streaming and async concurrency require careful design.** Combining a synchronous blocking library (CrewAI) with a streaming HTTP response required a background thread and a queue — a pattern that isn't obvious but maps cleanly once you understand the constraints.

- **Whisper improves with context.** Transcribing the full accumulated audio buffer on each chunk (rather than just the latest chunk) produces dramatically better results as more speech context becomes available.

---

_Built by Srija Chatterjee · [GitHub](https://github.com/srijachatterjee19)_
