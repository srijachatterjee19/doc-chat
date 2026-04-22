import { useState, useEffect, useRef } from 'react'

function getInitialTheme() {
  const stored = localStorage.getItem('theme')
  if (stored) return stored
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

export default function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [models, setModels] = useState([])
  const [selectedModel, setSelectedModel] = useState('')
  const [docCount, setDocCount] = useState(0)
  const [streaming, setStreaming] = useState(false)
  const [showMenu, setShowMenu] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [interrupted, setInterrupted] = useState(false)
  const [theme, setTheme] = useState(getInitialTheme)
  const bottomRef = useRef(null)
  const menuRef = useRef(null)
  const fileInputRef = useRef(null)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  useEffect(() => {
    fetch('/api/models')
      .then(r => r.json())
      .then(d => {
        setModels(d.models)
        setSelectedModel(d.models[0] ?? 'llama3.2')
      })
    fetch('/api/status')
      .then(r => r.json())
      .then(d => setDocCount(d.doc_count))
    fetch('/api/history')
      .then(r => r.json())
      .then(d => {
        const msgs = d.messages
        // If the last message is from the user, the previous response was interrupted
        if (msgs.length > 0 && msgs[msgs.length - 1].role === 'user') {
          fetch('/api/history/rollback', { method: 'POST' })
          setInterrupted(true)
        }
        setMessages(msgs)
      })
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setShowMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  async function sendMessage() {
    if (!input.trim() || streaming) return

    const userMsg = input.trim()
    setInput('')
    setInterrupted(false)
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])
    setStreaming(true)
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg, model: selectedModel }),
      })

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6).trim()
          if (data === '[DONE]') break
          try {
            const { text } = JSON.parse(data)
            setMessages(prev => {
              const msgs = [...prev]
              const last = msgs[msgs.length - 1]
              msgs[msgs.length - 1] = { ...last, content: last.content + text }
              return msgs
            })
          } catch {
            // malformed SSE chunk — skip
          }
        }
      }
    } finally {
      setStreaming(false)
    }
  }

  async function clearConversation() {
    await fetch('/api/reset', { method: 'POST' })
    setMessages([])
    setShowMenu(false)
  }

  function handleModelChange(model) {
    setSelectedModel(model)
    clearConversation()
  }

  async function handleUpload(e) {
    const file = e.target.files[0]
    if (!file) return
    e.target.value = ''
    setUploading(true)
    setShowMenu(false)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch('/api/upload', { method: 'POST', body: form })
      if (!res.ok) {
        const err = await res.json()
        alert(err.detail ?? 'Upload failed.')
        return
      }
      const { doc_count } = await res.json()
      setDocCount(doc_count)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="app">
      <main className="chat">
        <div className="chat-header">
          {docCount === 0 ? (
            <span className="header-warning">
              No documents loaded — run: <code>python ingest.py data/sample.txt</code>
            </span>
          ) : (
            <span className="header-doc-count">{docCount} document chunks loaded</span>
          )}

          <div className="header-actions">
            <button
              className="theme-btn"
              onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
              title="Toggle light/dark mode"
            >
              {theme === 'dark' ? '☀' : '☾'}
            </button>

            <div className="menu-container" ref={menuRef}>
              <button className="menu-btn" onClick={() => setShowMenu(v => !v)}>
                •••
              </button>
              {showMenu && (
                <div className="dropdown">
                  <button className="dropdown-item" onClick={() => fileInputRef.current.click()}>
                    {uploading ? 'Uploading…' : 'Upload document'}
                  </button>
                  <button className="dropdown-item" onClick={clearConversation}>
                    Clear conversation
                  </button>
                </div>
              )}
            </div>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.md,.pdf"
            style={{ display: 'none' }}
            onChange={handleUpload}
          />
        </div>

        <div className="messages">
          {messages.length === 0 && (
            <div className="empty-state">Ask a question about your documents</div>
          )}
          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              <div className="bubble">
                {msg.content || (streaming && i === messages.length - 1 ? '…' : '')}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {interrupted && (
          <div className="interrupted-notice">
            Sorry, your last message was interrupted. Please try again.
          </div>
        )}

        <div className="input-area">
          <select
            className="model-select"
            value={selectedModel}
            onChange={e => handleModelChange(e.target.value)}
            disabled={streaming}
          >
            {models.map(m => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
            placeholder="Ask a question about your documents..."
            disabled={streaming}
            autoFocus
          />
          <button
            className="send-btn"
            onClick={sendMessage}
            disabled={streaming || !input.trim()}
          >
            {streaming ? 'Sending…' : 'Send'}
          </button>
        </div>
      </main>
    </div>
  )
}
