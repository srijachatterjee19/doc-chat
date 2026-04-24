import { useRef, useState } from 'react'

function getSupportedMimeType() {
  const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg']
  return types.find(t => MediaRecorder.isTypeSupported(t)) ?? ''
}

export default function InputArea({ input, models, selectedModel, streaming, onInputChange, onModelChange, onSend }) {
  const [listening, setListening] = useState(false)
  const mediaRecorderRef = useRef(null)
  const wsRef = useRef(null)
  const streamRef = useRef(null)

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      const wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/transcribe`
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onmessage = e => {
        const { text } = JSON.parse(e.data)
        if (text) onInputChange(text)
      }

      ws.onerror = e => {
        console.error('Transcription WebSocket error', e)
        stopRecording()
      }

      ws.onopen = () => {
        const mimeType = getSupportedMimeType()
        const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : {})
        mediaRecorderRef.current = recorder

        recorder.ondataavailable = e => {
          if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
            ws.send(e.data)
          }
        }

        // Close the socket only after the last chunk has been sent
        recorder.onstop = () => {
          if (ws.readyState === WebSocket.OPEN) ws.close()
        }

        recorder.start(3000) // chunk every 3 s
        setListening(true)
      }
    } catch (err) {
      console.error('Mic error', err)
      alert('Microphone access denied or not available.')
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop() // triggers ondataavailable then onstop
    streamRef.current?.getTracks().forEach(t => t.stop())
    setListening(false)
  }

  function toggleMic() {
    listening ? stopRecording() : startRecording()
  }

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
        className={`mic-btn${listening ? ' mic-btn--active' : ''}`}
        onClick={toggleMic}
        disabled={streaming}
        title={listening ? 'Stop recording' : 'Speak your question'}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="9" y="2" width="6" height="12" rx="3" />
          <path d="M5 10a7 7 0 0 0 14 0" />
          <line x1="12" y1="19" x2="12" y2="22" />
          <line x1="8" y1="22" x2="16" y2="22" />
        </svg>
      </button>
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
