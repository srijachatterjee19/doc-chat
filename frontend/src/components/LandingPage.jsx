import React, { useEffect, useRef, useState, memo } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'motion/react'
import { ArrowRight, Menu, X } from 'lucide-react'
import Hls from 'hls.js'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faBolt, faMagnifyingGlass, faFileLines, faLink, faComments, faMoon } from '@fortawesome/free-solid-svg-icons'

const SRC = 'https://stream.mux.com/hUT6X11m1Vkw1QMxPOLgI761x2cfpi9bHFbi5cNg4014.m3u8'

const BackgroundVideo = memo(() => {
  const videoRef = useRef(null)

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = SRC
      video.play().catch(() => {})
    } else if (Hls.isSupported()) {
      const hls = new Hls({ enableWorker: true, lowLatencyMode: false })
      hls.loadSource(SRC)
      hls.attachMedia(video)
      hls.on(Hls.Events.MANIFEST_PARSED, () => video.play().catch(() => {}))
      hls.on(Hls.Events.ERROR, (_, data) => {
        if (!data.fatal) return
        if (data.type === Hls.ErrorTypes.NETWORK_ERROR) hls.startLoad()
        else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) hls.recoverMediaError()
        else hls.destroy()
      })
      return () => hls.destroy()
    }
  }, [])

  return (
    <video
      ref={videoRef}
      autoPlay
      loop
      muted
      playsInline
      style={{ position: 'fixed', inset: 0, width: '100%', height: '100%', objectFit: 'cover', zIndex: 1 }}
    />
  )
})

const GlowButton = ({ children, variant = 'primary', onClick }) => {
  const [isHovered, setIsHovered] = useState(false)

  if (variant === 'primary') {
    return (
      <motion.button
        onHoverStart={() => setIsHovered(true)}
        onHoverEnd={() => setIsHovered(false)}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.98 }}
        onClick={onClick}
        style={{
          position: 'relative',
          padding: '16px 32px',
          borderRadius: '9999px',
          fontWeight: 500,
          color: '#fff',
          overflow: 'hidden',
          background: 'linear-gradient(to right, #FF3300, #EE7926)',
          border: '1.5px solid rgba(255,255,255,0.2)',
          cursor: 'pointer',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: '16px',
        }}
      >
        <motion.div
          style={{ position: 'absolute', inset: 0, background: '#ea580c', filter: 'blur(16px)', zIndex: -1 }}
          animate={{ opacity: isHovered ? 0.6 : 0.2 }}
          transition={{ duration: 0.3 }}
        />
        {children}
        <motion.span
          animate={{ x: isHovered ? 0 : -20, opacity: isHovered ? 1 : 0 }}
          transition={{ duration: 0.3 }}
          style={{ display: 'flex' }}
        >
          <ArrowRight size={18} />
        </motion.span>
      </motion.button>
    )
  }

  return (
    <motion.button
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      style={{
        position: 'relative',
        padding: '16px 32px',
        borderRadius: '9999px',
        fontWeight: 500,
        color: '#000',
        overflow: 'hidden',
        background: 'rgba(255,255,255,0.9)',
        border: '1.5px solid rgba(0,0,0,0.05)',
        cursor: 'pointer',
        fontSize: '16px',
      }}
    >
      {children}
    </motion.button>
  )
}

export default function LandingPage() {
  const navigate = useNavigate()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.15, delayChildren: 0.3 },
    },
  }

  const itemVariants = {
    hidden: { opacity: 0, y: 30 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.8, ease: [0.22, 1, 0.36, 1] },
    },
  }

  const navLinkStyle = {
    color: 'rgba(255,255,255,0.8)',
    textDecoration: 'none',
    fontSize: '15px',
    transition: 'color 0.2s',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: 0,
  }

  useEffect(() => {
    document.body.style.overflow = 'auto'
    return () => { document.body.style.overflow = '' }
  }, [])

  return (
    <div style={{ position: 'relative', color: '#fff', fontFamily: 'Inter, sans-serif' }}>

      {/* Animated gradient — fixed so it stays while scrolling */}
      <div className="landing-bg" style={{ position: 'fixed' }} />

      {/* Background video — fixed so it stays while scrolling */}
      <BackgroundVideo />

      {/* Dark overlay — fixed */}
      <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 2 }} />

      {/* Top gradient bar */}
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, height: '5px', zIndex: 50,
        background: 'linear-gradient(to right, #ccf, #e7d04c, #31fb78)',
      }} />

      {/* Navbar */}
      <nav style={{ position: 'relative', zIndex: 30, padding: '24px 24px 0' }}>
        <div style={{ maxWidth: '1280px', margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.6 }}
            style={{ fontSize: '22px', fontWeight: 600, letterSpacing: '-0.02em' }}
          >
            DocChat
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            style={{ display: 'flex', alignItems: 'center', gap: '32px' }}
            className="landing-nav-links"
          >
            {['Features', 'Pricing'].map(item => (
              <a key={item} href={`#${item.toLowerCase()}`} style={navLinkStyle}>{item}</a>
            ))}
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
            className="landing-nav-links"
          >
            <button
              onClick={() => navigate('/login')}
              style={{ ...navLinkStyle, padding: '10px 20px' }}
            >
              Sign In
            </button>
            <button
              onClick={() => navigate('/signup')}
              style={{
                padding: '10px 20px',
                background: 'rgba(255,255,255,0.1)',
                backdropFilter: 'blur(8px)',
                border: '1px solid rgba(255,255,255,0.2)',
                borderRadius: '9999px',
                color: '#fff',
                cursor: 'pointer',
                fontSize: '15px',
              }}
            >
              Sign Up
            </button>
          </motion.div>

          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            style={{ ...navLinkStyle, display: 'none' }}
            className="landing-menu-btn"
          >
            {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>

        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            style={{
              marginTop: '16px',
              background: 'rgba(0,0,0,0.8)',
              backdropFilter: 'blur(20px)',
              borderRadius: '16px',
              padding: '24px',
              border: '1px solid rgba(255,255,255,0.1)',
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {['Features', 'Pricing'].map(item => (
                <a key={item} href={`#${item.toLowerCase()}`} style={navLinkStyle}>{item}</a>
              ))}
              <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <button onClick={() => navigate('/login')} style={navLinkStyle}>Sign In</button>
                <button onClick={() => navigate('/signup')} style={{
                  padding: '10px 20px', background: 'rgba(255,255,255,0.1)',
                  border: '1px solid rgba(255,255,255,0.2)', borderRadius: '9999px',
                  color: '#fff', cursor: 'pointer', fontSize: '15px',
                }}>Sign Up</button>
              </div>
            </div>
          </motion.div>
        )}
      </nav>

      {/* Hero */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        style={{ position: 'relative', zIndex: 30, maxWidth: '900px', margin: '0 auto', padding: '80px 24px 128px', textAlign: 'center' }}
      >
        <motion.h1
          variants={itemVariants}
          style={{ fontSize: 'clamp(48px, 8vw, 96px)', fontWeight: 700, lineHeight: 0.95, marginBottom: '24px', letterSpacing: '-0.03em' }}
        >
          Ask questions about your documents, get answers instantly
        </motion.h1>

        <motion.p
          variants={itemVariants}
          style={{ fontSize: 'clamp(16px, 2.5vw, 22px)', color: 'rgba(255,255,255,0.85)', marginBottom: '48px', maxWidth: '600px', margin: '0 auto 48px', lineHeight: 1.6 }}
        >
          DocChat uses AI to search your files and give grounded, accurate answers in seconds.
        </motion.p>

        <motion.div
          variants={itemVariants}
          style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'center', gap: '16px', marginBottom: '64px' }}
        >
          <GlowButton variant="primary" onClick={() => navigate('/signup')}>Get Started Free</GlowButton>
          <GlowButton variant="secondary" onClick={() => navigate('/login')}>Sign In</GlowButton>
        </motion.div>

      </motion.div>

      {/* Features */}
      <section id="features" style={{ position: 'relative', zIndex: 30, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(24px)', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
        <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '96px 24px' }}>
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
            style={{ textAlign: 'center', marginBottom: '64px' }}
          >
            <span style={{
              display: 'inline-block', fontSize: '12px', fontWeight: 600,
              letterSpacing: '0.12em', textTransform: 'uppercase',
              color: '#ea580c', marginBottom: '16px',
            }}>
              Features
            </span>
            <h2 style={{ fontSize: 'clamp(32px, 5vw, 52px)', fontWeight: 700, letterSpacing: '-0.03em', lineHeight: 1.1, color: '#fff' }}>
              Everything you need to chat<br />with your documents
            </h2>
          </motion.div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px' }}>
            {[
              {
                icon: faBolt,
                title: 'Streaming responses',
                desc: 'Answers start appearing instantly as the model generates them — no waiting for the full response.',
              },
              {
                icon: faMagnifyingGlass,
                title: 'Semantic search',
                desc: 'Finds the most relevant chunks of your documents using vector similarity, not just keyword matching.',
              },
              {
                icon: faFileLines,
                title: 'Multi-document support',
                desc: 'Upload PDFs, text files, and markdown. Ask questions that span across multiple documents at once.',
              },
              {
                icon: faLink,
                title: 'Grounded answers',
                desc: 'Every response is grounded in your actual content — the model can\'t hallucinate facts that aren\'t in your files.',
              },
              {
                icon: faComments,
                title: 'Conversation memory',
                desc: 'Follow-up questions are automatically rewritten to preserve context from earlier in the conversation.',
              },
              {
                icon: faMoon,
                title: 'Dark & light mode',
                desc: 'Comfortable to use at any time of day. Respects your system preference and remembers your choice.',
              },
            ].map((feature, i) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: i * 0.08, ease: [0.22, 1, 0.36, 1] }}
                style={{
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '16px',
                  padding: '32px',
                  transition: 'border-color 0.2s',
                }}
                whileHover={{ borderColor: 'rgba(234,88,12,0.4)', backgroundColor: 'rgba(255,255,255,0.06)' }}
              >
                <div style={{
                  width: '44px', height: '44px', borderRadius: '12px',
                  background: 'rgba(234,88,12,0.15)', border: '1px solid rgba(234,88,12,0.25)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  marginBottom: '20px',
                }}>
                  <FontAwesomeIcon icon={feature.icon} style={{ fontSize: '18px', color: '#ea580c' }} />
                </div>
                <h3 style={{ fontSize: '17px', fontWeight: 600, color: '#fff', marginBottom: '10px', letterSpacing: '-0.01em' }}>
                  {feature.title}
                </h3>
                <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.55)', lineHeight: 1.7 }}>
                  {feature.desc}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" style={{ position: 'relative', zIndex: 30, borderTop: '1px solid rgba(255,255,255,0.08)' }}>
        <div style={{ maxWidth: '900px', margin: '0 auto', padding: '96px 24px' }}>
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
            style={{ textAlign: 'center', marginBottom: '64px' }}
          >
            <span style={{
              display: 'inline-block', fontSize: '12px', fontWeight: 600,
              letterSpacing: '0.12em', textTransform: 'uppercase',
              color: '#ea580c', marginBottom: '16px',
            }}>
              Pricing
            </span>
            <h2 style={{ fontSize: 'clamp(32px, 5vw, 52px)', fontWeight: 700, letterSpacing: '-0.03em', lineHeight: 1.1, color: '#fff' }}>
              Simple, transparent pricing
            </h2>
          </motion.div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '24px', alignItems: 'start' }}>
            {[
              {
                name: 'Free',
                price: '₹0',
                period: '/ month',
                features: ['10 messages per day', 'Up to 2 documents', 'Standard response speed'],
                cta: 'Get started',
                pro: false,
              },
              {
                name: 'Pro',
                price: '₹799',
                period: '/ month',
                features: ['Unlimited messages', 'Unlimited documents', 'Priority response speed', 'Early access to new features'],
                cta: 'Upgrade to Pro',
                pro: true,
              },
            ].map((plan, i) => (
              <motion.div
                key={plan.name}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: i * 0.1, ease: [0.22, 1, 0.36, 1] }}
                style={{
                  position: 'relative',
                  background: plan.pro ? 'rgba(234,88,12,0.08)' : 'rgba(255,255,255,0.04)',
                  border: `1px solid ${plan.pro ? 'rgba(234,88,12,0.5)' : 'rgba(255,255,255,0.08)'}`,
                  borderRadius: '20px',
                  padding: '36px 32px',
                }}
              >
                {plan.pro && (
                  <div style={{
                    position: 'absolute', top: '-13px', left: '50%', transform: 'translateX(-50%)',
                    background: '#ea580c', color: '#fff', fontSize: '11px', fontWeight: 700,
                    padding: '4px 14px', borderRadius: '20px', letterSpacing: '0.06em', textTransform: 'uppercase',
                    whiteSpace: 'nowrap',
                  }}>
                    Most popular
                  </div>
                )}

                <p style={{ fontSize: '12px', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: plan.pro ? '#ea580c' : 'rgba(255,255,255,0.5)', marginBottom: '12px' }}>
                  {plan.name}
                </p>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px', marginBottom: '28px' }}>
                  <span style={{ fontSize: '44px', fontWeight: 700, color: '#fff', letterSpacing: '-2px' }}>{plan.price}</span>
                  <span style={{ fontSize: '14px', color: 'rgba(255,255,255,0.45)' }}>{plan.period}</span>
                </div>

                <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 32px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {plan.features.map(f => (
                    <li key={f} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '14px', color: 'rgba(255,255,255,0.75)' }}>
                      <span style={{ color: '#ea580c', fontWeight: 700, fontSize: '13px' }}>✓</span>
                      {f}
                    </li>
                  ))}
                </ul>

                <motion.button
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  onClick={() => navigate('/signup')}
                  style={{
                    width: '100%', padding: '12px', borderRadius: '10px', fontSize: '14px', fontWeight: 600,
                    cursor: 'pointer', border: 'none',
                    background: plan.pro ? '#ea580c' : 'rgba(255,255,255,0.08)',
                    color: '#fff',
                  }}
                >
                  {plan.cta}
                </motion.button>
              </motion.div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
