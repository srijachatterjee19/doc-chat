import { useState, useEffect } from 'react'
import { track } from '../analytics'

export default function SignupPage({ onGoToLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { track('signup_view') }, [])

  function handleSubmit(e) {
    e.preventDefault()
    if (!username.trim()) { setError('Username is required.'); return }
    if (password.length < 4) { setError('Password must be at least 4 characters.'); return }
    if (password !== confirm) { setError('Passwords do not match.'); return }
    track('signup')
    setSubmitted(true)
  }

  if (submitted) {
    return (
      <div className="auth-page">
        <div className="auth-panel auth-panel--brand">
          <div className="auth-brand">
            <h1 className="auth-brand-name">DocChat</h1>
            <p className="auth-brand-tagline">Ask questions about your documents.</p>
          </div>
        </div>

        <div className="auth-panel auth-panel--form">
          <div className="auth-form-wrap">
            <div className="auth-success-icon">✓</div>
            <h2 className="auth-heading">Account created</h2>
            <p className="auth-subheading">Authentication is coming soon.</p>
            <button className="auth-submit" style={{ marginTop: '32px' }} onClick={onGoToLogin}>
              Back to sign in
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="auth-page">
      <div className="auth-panel auth-panel--brand">
        <div className="auth-brand">
          <h1 className="auth-brand-name">DocChat</h1>
          <p className="auth-brand-tagline">Ask questions about your documents.</p>
        </div>
      </div>

      <div className="auth-panel auth-panel--form">
        <div className="auth-form-wrap">
          <h2 className="auth-heading">Create an account</h2>
          <p className="auth-subheading">Get started for free</p>

          <form className="auth-form" onSubmit={handleSubmit}>
            <div className="auth-field">
              <label className="auth-label">Username</label>
              <input
                className="auth-input"
                type="text"
                value={username}
                onChange={e => { setUsername(e.target.value); setError('') }}
                placeholder="Choose a username"
                autoFocus
                autoComplete="username"
              />
            </div>
            <div className="auth-field">
              <label className="auth-label">Password</label>
              <input
                className="auth-input"
                type="password"
                value={password}
                onChange={e => { setPassword(e.target.value); setError('') }}
                placeholder="Create a password"
                autoComplete="new-password"
              />
            </div>
            <div className="auth-field">
              <label className="auth-label">Confirm password</label>
              <input
                className="auth-input"
                type="password"
                value={confirm}
                onChange={e => { setConfirm(e.target.value); setError('') }}
                placeholder="Repeat your password"
                autoComplete="new-password"
              />
            </div>

            {error && <p className="auth-error">{error}</p>}

            <button className="auth-submit" type="submit">Create account</button>
          </form>

          <p className="auth-switch">
            Already have an account?{' '}
            <button className="auth-link" onClick={onGoToLogin}>Sign in</button>
          </p>
        </div>
      </div>
    </div>
  )
}
