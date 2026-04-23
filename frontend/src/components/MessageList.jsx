import { useRef, useEffect, useState } from 'react'

export default function MessageList({ messages, streaming, interrupted }) {
  const bottomRef = useRef(null)
  const messagesRef = useRef(null)
  const [showScrollTop, setShowScrollTop] = useState(false)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

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
          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              <div className="bubble">
                {msg.content || (streaming && i === messages.length - 1 ? '…' : '')}
              </div>
            </div>
          ))}
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
