import { useRef, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faMicrophone, faCircleStop, faSpinner } from '@fortawesome/free-solid-svg-icons'

export default function InputArea({ input, streaming, onInputChange, onSend }) {
  const [recording, setRecording] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])

  async function startRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const recorder = new MediaRecorder(stream)
    chunksRef.current = []
    recorder.ondataavailable = e => chunksRef.current.push(e.data)
    recorder.onstop = async () => {
      stream.getTracks().forEach(track => track.stop())
      setTranscribing(true)
      try {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType })
        const form = new FormData()
        form.append('file', blob, 'recording.webm')
        const res = await fetch('/api/stt', { method: 'POST', body: form })
        if (!res.ok) {
          const err = await res.json()
          alert(err.detail ?? 'Transcription failed.')
          return
        }
        const { transcript } = await res.json()
        if (transcript) {
          onInputChange(prev => (prev ? `${prev} ${transcript}` : transcript))
        }
      } finally {
        setTranscribing(false)
      }
    }
    mediaRecorderRef.current = recorder
    recorder.start()
    setRecording(true)
  }

  function toggleRecording() {
    if (recording) {
      mediaRecorderRef.current?.stop()
      setRecording(false)
    } else {
      startRecording()
    }
  }

  return (
    <div className="input-area">
      <button
        type="button"
        className={`mic-btn${recording ? ' mic-btn--active' : ''}`}
        onClick={toggleRecording}
        disabled={streaming || transcribing}
        title={recording ? 'Stop recording' : 'Speak your question'}
      >
        <FontAwesomeIcon
          icon={transcribing ? faSpinner : recording ? faCircleStop : faMicrophone}
          spin={transcribing}
        />
      </button>
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
