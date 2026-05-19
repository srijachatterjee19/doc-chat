import { useRef, useEffect, useState } from 'react'

export default function ChatHeader({ docCount, documents, theme, onToggleTheme, onClearConversation, onLogout, onGoToPricing }) {
  const [showMenu, setShowMenu] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setShowMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div className="chat-header">
      {docCount > 0 && (
        <span className="header-doc-count">
          {docCount} chunks across {documents.length} file{documents.length !== 1 ? 's' : ''}
        </span>
      )}

      <div className="header-actions">
        <button
          className="theme-btn"
          onClick={onToggleTheme}
          title="Toggle light/dark mode"
        >
          {theme === 'dark' ? '☀' : '☾'}
        </button>

        <div className="menu-container" ref={menuRef}>
          <button className="menu-btn" onClick={() => setShowMenu(v => !v)}>
            •••
          </button>
          {showMenu && (
            <div className="dropdown">
              <button
                className="dropdown-item"
                onClick={() => { setShowMenu(false); onGoToPricing() }}
              >
                Upgrade to Pro
              </button>
              <button
                className="dropdown-item"
                onClick={() => { onClearConversation(); setShowMenu(false) }}
              >
                Clear conversation
              </button>
              <button
                className="dropdown-item dropdown-item--danger"
                onClick={() => { setShowMenu(false); onLogout() }}
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
