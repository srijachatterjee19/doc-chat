import { useRef, useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faVolumeHigh, faCircleStop, faSpinner } from '@fortawesome/free-solid-svg-icons'

function stripMarkdown(text) {
  return text
    .replace(/```[\s\S]*?```/g, '')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/[*_#>~]/g, '')
    .trim()
}

function AgentCard({ agent, icon, summary, status }) {
  return (
    <div className={`agent-card agent-card--${status}`}>
      <span className="agent-card__icon">{icon}</span>
      <div className="agent-card__body">
        <span className="agent-card__name">{agent}</span>
        <span className="agent-card__summary">{summary}</span>
      </div>
      <span className="agent-card__dot" />
    </div>
  )
}

export default function MessageList({ messages, streaming, interrupted, agentUpdates = [] }) {
  const bottomRef = useRef(null)
  const messagesRef = useRef(null)
  const [showScrollTop, setShowScrollTop] = useState(false)
  const [speakingIndex, setSpeakingIndex] = useState(null)
  const [loadingIndex, setLoadingIndex] = useState(null)
  const audioRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, agentUpdates])

  useEffect(() => {
    return () => audioRef.current?.pause()
  }, [])

  function stopSpeaking() {
    audioRef.current?.pause()
    audioRef.current = null
    setSpeakingIndex(null)
  }

  async function toggleSpeak(i, text) {
    if (speakingIndex === i || loadingIndex === i) {
      stopSpeaking()
      setLoadingIndex(null)
      return
    }
    stopSpeaking()
    setLoadingIndex(i)
    try {
      const res = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: stripMarkdown(text) }),
      })
      if (!res.ok) {
        const err = await res.json()
        alert(err.detail ?? 'Text-to-speech failed.')
        return
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      audio.onended = () => { stopSpeaking(); URL.revokeObjectURL(url) }
      audio.onerror = () => { stopSpeaking(); URL.revokeObjectURL(url) }
      audioRef.current = audio
      setSpeakingIndex(i)
      await audio.play()
    } finally {
      setLoadingIndex(null)
    }
  }

  useEffect(() => {
    const el = messagesRef.current
    if (!el) return
    const handleScroll = () => setShowScrollTop(el.scrollTop > 200)
    el.addEventListener('scroll', handleScroll)
    return () => el.removeEventListener('scroll', handleScroll)
  }, [])

  return (
    <>
      <div className="messages-wrapper">
        <div className="messages" ref={messagesRef}>
          {messages.length === 0 && (
            <div className="empty-state">Ask a question about your documents</div>
          )}
          {messages.map((msg, i) => {
            const isLastAssistant = msg.role === 'assistant' && i === messages.length - 1
            return (
              <div key={i}>
                {isLastAssistant && agentUpdates.length > 0 && (
                  <div className="agent-activity">
                    {agentUpdates.map(u => (
                      <AgentCard key={u.agent} {...u} />
                    ))}
                  </div>
                )}
                <div className={`message ${msg.role}`}>
                  <div className="bubble">
                    {msg.role === 'assistant' ? (
                      msg.content
                        ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                        : streaming && isLastAssistant ? <span className="typing-dot">…</span> : ''
                    ) : (
                      msg.content
                    )}
                  </div>
                  {msg.role === 'assistant' && msg.content && (
                    <button
                      className={`speaker-btn${speakingIndex === i ? ' speaker-btn--active' : ''}`}
                      onClick={() => toggleSpeak(i, msg.content)}
                      title={speakingIndex === i ? 'Stop reading' : 'Read aloud'}
                    >
                      <FontAwesomeIcon
                        icon={loadingIndex === i ? faSpinner : speakingIndex === i ? faCircleStop : faVolumeHigh}
                        spin={loadingIndex === i}
                      />
                    </button>
                  )}
                </div>
              </div>
            )
          })}
          <div ref={bottomRef} />
        </div>

        {showScrollTop && (
          <button
            className="scroll-top-btn"
            onClick={() => messagesRef.current?.scrollTo({ top: 0, behavior: 'smooth' })}
            title="Scroll to top"
          >
            ↑
          </button>
        )}
      </div>

      {interrupted && (
        <div className="interrupted-notice">
          Sorry, your last message was interrupted. Please try again.
        </div>
      )}
    </>
  )
}
