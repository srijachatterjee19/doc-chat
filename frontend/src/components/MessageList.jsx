import { useRef, useEffect, useState } from 'react'

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

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, agentUpdates])

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
                    {msg.content || (streaming && isLastAssistant ? '…' : '')}
                  </div>
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
