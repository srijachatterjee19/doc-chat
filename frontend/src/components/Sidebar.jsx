export default function Sidebar({ documents, uploading, fileInputRef, onUpload, onDocClick }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <span className="sidebar-title">Documents</span>
        <button
          className="upload-btn"
          onClick={() => fileInputRef.current.click()}
          disabled={uploading}
          title="Upload document"
        >
          {uploading ? '…' : '+'}
        </button>
      </div>

      <div className="sidebar-docs">
        {documents.length === 0 ? (
          <p className="sidebar-empty">No documents yet</p>
        ) : (
          documents.map(doc => {
            const isPdf = doc.name.toLowerCase().endsWith('.pdf')
            return (
              <div
                key={doc.name}
                className="doc-item"
                onClick={() => isPdf
                  ? window.open(`/api/files/${encodeURIComponent(doc.name)}`, '_blank')
                  : onDocClick(doc.name)
                }
                title={isPdf ? `View ${doc.name}` : `Ask about ${doc.name}`}
              >
                <span className="doc-icon">{isPdf ? '📄' : '⬡'}</span>
                <span className="doc-name">{doc.name}</span>
                <span className="doc-chunks">{doc.chunks}</span>
              </div>
            )
          })
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".txt,.md,.pdf"
        style={{ display: 'none' }}
        onChange={onUpload}
      />
    </aside>
  )
}
