import { useRef, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faMicrophone, faCircleStop } from '@fortawesome/free-solid-svg-icons'

const SpeechRecognitionAPI =
  typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition)

export default function InputArea({ input, streaming, onInputChange, onSend }) {
  const [listening, setListening] = useState(false)
  const recognitionRef = useRef(null)

  function toggleListening() {
    if (!SpeechRecognitionAPI) return
    if (listening) {
      recognitionRef.current?.stop()
      return
    }
    const recognition = new SpeechRecognitionAPI()
    recognition.lang = 'en-US'
    recognition.interimResults = false
    recognition.maxAlternatives = 1
    recognition.onresult = e => {
      const transcript = e.results[0][0].transcript
      onInputChange(prev => (prev ? `${prev} ${transcript}` : transcript))
    }
    recognition.onend = () => setListening(false)
    recognition.onerror = () => setListening(false)
    recognitionRef.current = recognition
    recognition.start()
    setListening(true)
  }

  return (
    <div className="input-area">
      {SpeechRecognitionAPI && (
        <button
          type="button"
          className={`mic-btn${listening ? ' mic-btn--active' : ''}`}
          onClick={toggleListening}
          disabled={streaming}
          title={listening ? 'Stop recording' : 'Speak your question'}
        >
          <FontAwesomeIcon icon={listening ? faCircleStop : faMicrophone} />
        </button>
      )}
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
