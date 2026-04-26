export default function InputArea({ input, streaming, onInputChange, onSend }) {
  return (
    <div className="input-area">
      <input
        value={input}
        onChange={e => onInputChange(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && !e.shiftKey && onSend()}
        placeholder="Ask a question about your documents..."
        disabled={streaming}
        autoFocus
      />
      <button
        className="send-btn"
        onClick={onSend}
        disabled={streaming || !input.trim()}
      >
        {streaming ? 'Sending…' : 'Send'}
      </button>
    </div>
  )
}
