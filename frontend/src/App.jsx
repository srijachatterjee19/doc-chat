import { useState, useEffect, useRef } from 'react'
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { track } from './analytics'
import Sidebar from './components/Sidebar'
import ChatHeader from './components/ChatHeader'
import MessageList from './components/MessageList'
import InputArea from './components/InputArea'
import LoginPage from './components/LoginPage'
import SignupPage from './components/SignupPage'
import PricingPage from './components/PricingPage'
import LandingPage from './components/LandingPage'

function getSessionId() {
  let id = localStorage.getItem('sessionId')
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem('sessionId', id)
  }
  return id
}

function getInitialTheme() {
  const stored = localStorage.getItem('theme')
  if (stored) return stored
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

function isLoggedIn() {
  return !!localStorage.getItem('loggedIn')
}

function ProtectedRoute({ children }) {
  return isLoggedIn() ? children : <Navigate to="/login" replace />
}

function ChatApp() {
  const navigate = useNavigate()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [docCount, setDocCount] = useState(0)
  const [documents, setDocuments] = useState([])
  const [streaming, setStreaming] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [interrupted, setInterrupted] = useState(false)
  const [agentUpdates, setAgentUpdates] = useState([])
  const [theme, setTheme] = useState(getInitialTheme)
  const fileInputRef = useRef(null)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  async function refreshDocuments() {
    const d = await fetch('/api/documents').then(r => r.json())
    setDocuments(d.documents)
    setDocCount(d.documents.reduce((sum, doc) => sum + doc.chunks, 0))
  }

  useEffect(() => {
    refreshDocuments()
    fetch(`/api/history?session_id=${getSessionId()}`)
      .then(r => r.json())
      .then(d => {
        const msgs = d.messages
        if (msgs.length > 0 && msgs[msgs.length - 1].role === 'user') {
          fetch(`/api/history/rollback?session_id=${getSessionId()}`, { method: 'POST' })
          setInterrupted(true)
        }
        setMessages(msgs)
      })
  }, [])

  async function sendMessage() {
    if (!input.trim() || streaming) return
    const userMsg = input.trim()
    track(messages.length === 0 ? 'first_message' : 'send_message')
    setInput('')
    setInterrupted(false)
    setAgentUpdates([])
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])
    setStreaming(true)
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])
    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg, session_id: getSessionId() }),
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
            const parsed = JSON.parse(data)
            if (parsed.type === 'agent_update') {
              setAgentUpdates(prev => {
                const idx = prev.findIndex(u => u.agent === parsed.agent)
                if (idx >= 0) {
                  const next = [...prev]
                  next[idx] = parsed
                  return next
                }
                return [...prev, parsed]
              })
            } else if (parsed.text) {
              setMessages(prev => {
                const msgs = [...prev]
                const last = msgs[msgs.length - 1]
                msgs[msgs.length - 1] = { ...last, content: last.content + parsed.text }
                return msgs
              })
            }
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
    await fetch(`/api/reset?session_id=${getSessionId()}`, { method: 'POST' })
    setMessages([])
    track('clear_conversation')
  }

  async function handleDeleteDoc(filename) {
    const res = await fetch(`/api/documents/${encodeURIComponent(filename)}`, { method: 'DELETE' })
    if (res.ok) {
      track('delete_document', { filename })
      await refreshDocuments()
    }
  }

  async function handleUpload(e) {
    const file = e.target.files[0]
    if (!file) return
    e.target.value = ''
    setUploading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch('/api/upload', { method: 'POST', body: form })
      if (!res.ok) {
        const err = await res.json()
        alert(err.detail ?? 'Upload failed.')
        return
      }
      track('upload_document', { file_type: file.type })
      window.location.reload()
    } finally {
      setUploading(false)
    }
  }

  function handleLogout() {
    localStorage.removeItem('loggedIn')
    track('logout')
    navigate('/login')
  }

  return (
    <div className="app">
      <Sidebar
        documents={documents}
        uploading={uploading}
        fileInputRef={fileInputRef}
        onUpload={handleUpload}
        onDocClick={name => setInput(`What is ${name} about?`)}
        onDeleteDoc={handleDeleteDoc}
      />
      <main className="chat">
        <ChatHeader
          docCount={docCount}
          documents={documents}
          theme={theme}
          onToggleTheme={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
          onClearConversation={clearConversation}
          onLogout={handleLogout}
          onGoToPricing={() => navigate('/pricing')}
        />
        <MessageList messages={messages} streaming={streaming} interrupted={interrupted} agentUpdates={agentUpdates} />
        <InputArea
          input={input}
          streaming={streaming}
          onInputChange={setInput}
          onSend={sendMessage}
        />
      </main>
    </div>
  )
}

function LoginWrapper() {
  const navigate = useNavigate()
  function handleLogin() {
    localStorage.setItem('loggedIn', '1')
    track('login')
    navigate('/chat')
  }
  return <LoginPage onLogin={handleLogin} onGoToSignup={() => navigate('/signup')} />
}

function SignupWrapper() {
  const navigate = useNavigate()
  return <SignupPage onGoToLogin={() => navigate('/login')} />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginWrapper />} />
      <Route path="/signup" element={<SignupWrapper />} />
      <Route path="/chat" element={<ProtectedRoute><ChatApp /></ProtectedRoute>} />
      <Route path="/pricing" element={<ProtectedRoute><PricingPage /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
