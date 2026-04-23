import { useState } from 'react'

export default function LoginPage({ onLogin, onGoToSignup }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    if (username === 'admin' && password === 'admin') {
      onLogin()
    } else {
      setError('Invalid username or password.')
    }
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
          <h2 className="auth-heading">Welcome back</h2>
          <p className="auth-subheading">Sign in to your account</p>

          <form className="auth-form" onSubmit={handleSubmit}>
            <div className="auth-field">
              <label className="auth-label">Username</label>
              <input
                className="auth-input"
                type="text"
                value={username}
                onChange={e => { setUsername(e.target.value); setError('') }}
                placeholder="Enter your username"
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
                placeholder="Enter your password"
                autoComplete="current-password"
              />
            </div>

            {error && <p className="auth-error">{error}</p>}

            <button className="auth-submit" type="submit">Sign in</button>
          </form>

          <p className="auth-switch">
            Don't have an account?{' '}
            <button className="auth-link" onClick={onGoToSignup}>Create one</button>
          </p>
        </div>
      </div>
    </div>
  )
}
