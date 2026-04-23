export default function InputArea({ input, models, selectedModel, streaming, onInputChange, onModelChange, onSend }) {
  return (
    <div className="input-area">
      <select
        className="model-select"
        value={selectedModel}
        onChange={e => onModelChange(e.target.value)}
        disabled={streaming}
      >
        {models.map(m => (
          <option key={m} value={m}>{m}</option>
        ))}
      </select>
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
