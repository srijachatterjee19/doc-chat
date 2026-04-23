import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const FEATURES_FREE = [
  '10 messages per day',
  'Up to 2 documents',
  'Standard response speed',
]

const FEATURES_PRO = [
  'Unlimited messages',
  'Unlimited documents',
  'Priority response speed',
  'Early access to new features',
]

function CheckoutModal({ onConfirm, onClose }) {
  const [cardNumber, setCardNumber] = useState('')
  const [expiry, setExpiry] = useState('')
  const [cvv, setCvv] = useState('')
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)

  function formatCardNumber(val) {
    return val.replace(/\D/g, '').slice(0, 16).replace(/(.{4})/g, '$1 ').trim()
  }

  function formatExpiry(val) {
    const digits = val.replace(/\D/g, '').slice(0, 4)
    return digits.length > 2 ? digits.slice(0, 2) + ' / ' + digits.slice(2) : digits
  }

  async function handlePay(e) {
    e.preventDefault()
    setLoading(true)
    await new Promise(r => setTimeout(r, 1500))
    setLoading(false)
    onConfirm()
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <p className="modal-label">SANDBOX MODE</p>
            <h2 className="modal-title">DocChat Pro — ₹799/mo</h2>
          </div>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <form className="modal-form" onSubmit={handlePay}>
          <div className="auth-field">
            <label className="auth-label">Cardholder name</label>
            <input className="auth-input" placeholder="Name on card" value={name} onChange={e => setName(e.target.value)} required />
          </div>
          <div className="auth-field">
            <label className="auth-label">Card number</label>
            <input className="auth-input" placeholder="4242 4242 4242 4242" value={cardNumber} onChange={e => setCardNumber(formatCardNumber(e.target.value))} required />
          </div>
          <div className="modal-row">
            <div className="auth-field">
              <label className="auth-label">Expiry</label>
              <input className="auth-input" placeholder="MM / YY" value={expiry} onChange={e => setExpiry(formatExpiry(e.target.value))} required />
            </div>
            <div className="auth-field">
              <label className="auth-label">CVV</label>
              <input className="auth-input" placeholder="•••" maxLength={3} value={cvv} onChange={e => setCvv(e.target.value.replace(/\D/g, '').slice(0, 3))} required />
            </div>
          </div>

          <div className="modal-sandbox-note">
            Sandbox mode — no real payment will be charged.
          </div>

          <button className="pricing-btn pricing-btn--pro" type="submit" disabled={loading}>
            {loading ? 'Processing…' : 'Pay ₹799'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default function PricingPage() {
  const navigate = useNavigate()
  const [tier, setTier] = useState(() => localStorage.getItem('subscriptionTier') || 'free')
  const [showCheckout, setShowCheckout] = useState(false)
  const [justUpgraded, setJustUpgraded] = useState(false)

  async function handleConfirm() {
    await fetch('/api/payments/subscribe', { method: 'POST' })
    localStorage.setItem('subscriptionTier', 'pro')
    setTier('pro')
    setJustUpgraded(true)
    setShowCheckout(false)
  }

  function handleDowngrade() {
    localStorage.removeItem('subscriptionTier')
    setTier('free')
    setJustUpgraded(false)
  }

  return (
    <div className="pricing-page">
      {showCheckout && (
        <CheckoutModal onConfirm={handleConfirm} onClose={() => setShowCheckout(false)} />
      )}

      <div className="pricing-header">
        <button className="pricing-back" onClick={() => navigate('/chat')}>← Back to chat</button>
        <h1 className="pricing-title">Plans &amp; Pricing</h1>
        <p className="pricing-subtitle">Choose the plan that fits your needs</p>
      </div>

      {justUpgraded && (
        <div className="pricing-success">
          You're now on Pro. Enjoy unlimited access!
        </div>
      )}

      <div className="pricing-cards">
        <div className={`pricing-card ${tier === 'free' ? 'pricing-card--current' : ''}`}>
          <div className="pricing-card-header">
            <span className="pricing-plan-name">Free</span>
            <div className="pricing-price">
              <span className="pricing-amount">₹0</span>
              <span className="pricing-period">/ month</span>
            </div>
          </div>
          <ul className="pricing-features">
            {FEATURES_FREE.map(f => (
              <li key={f}><span className="pricing-check">✓</span>{f}</li>
            ))}
          </ul>
          <div className="pricing-card-footer">
            {tier === 'free' ? (
              <span className="pricing-current-badge">Current plan</span>
            ) : (
              <button className="pricing-btn pricing-btn--outline" onClick={handleDowngrade}>
                Switch to Free
              </button>
            )}
          </div>
        </div>

        <div className={`pricing-card pricing-card--pro ${tier === 'pro' ? 'pricing-card--current' : ''}`}>
          <div className="pricing-badge">Most popular</div>
          <div className="pricing-card-header">
            <span className="pricing-plan-name">Pro</span>
            <div className="pricing-price">
              <span className="pricing-amount">₹799</span>
              <span className="pricing-period">/ month</span>
            </div>
          </div>
          <ul className="pricing-features">
            {FEATURES_PRO.map(f => (
              <li key={f}><span className="pricing-check">✓</span>{f}</li>
            ))}
          </ul>
          <div className="pricing-card-footer">
            {tier === 'pro' ? (
              <span className="pricing-current-badge">Current plan</span>
            ) : (
              <button className="pricing-btn pricing-btn--pro" onClick={() => setShowCheckout(true)}>
                Upgrade to Pro
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
