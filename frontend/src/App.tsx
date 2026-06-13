import { useState, useRef, useEffect } from 'react'
import { streamRAG, ingestFile, ingestURL, listDocs, deleteDoc, synthesiseTTS } from './api'
import type { Source, Doc, DocsResponse } from './api'
import './styles/globals.css'

interface Message {
  id: number
  role: 'user' | 'assistant'
  text: string
  sources?: Source[]
  latency_ms?: number
  streaming?: boolean
}

const ACCEPTED_TYPES = '.pdf,.txt,.md'

let _msgId = 0

function formatIngestResult(name: string, res: { chunks: number; latency_ms: number; status: string; detail: string }) {
  if (res.chunks > 0) {
    return `✓ ${name}: ${res.chunks} chunks (${res.latency_ms}ms)`
  }
  const reason = res.detail || res.status
  return `⚠ ${name}: 0 chunks — ${reason}`
}

export default function App() {
  const [messages,  setMessages]  = useState<Message[]>([])
  const [input,     setInput]     = useState('')
  const [loading,   setLoading]   = useState(false)
  const [docs,      setDocs]      = useState<Doc[]>([])
  const [dbWarning, setDbWarning] = useState<string | null>(null)
  const [ingestLog, setIngestLog] = useState<string[]>([])
  const [dragging,  setDragging]  = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<{ docId: string; source: string } | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const cleanupRef = useRef<(() => void) | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { loadDocs() }, [])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])
  useEffect(() => {
    return () => { cleanupRef.current?.() }
  }, [])

  async function loadDocs() {
    try {
      const response = await listDocs()
      setDocs(response.docs)
      setDbWarning(response.warning || null)
    } catch { /* ignore */ }
  }

  async function handleSend() {
    if (!input.trim() || loading) return
    cleanupRef.current?.()
    const query = input.trim()
    setInput('')
    setLoading(true)

    const userMsg: Message = { id: ++_msgId, role: 'user', text: query }
    const assistantMsg: Message = { id: ++_msgId, role: 'assistant', text: '', streaming: true }

    setMessages(prev => [...prev, userMsg, assistantMsg])

    let accumulated = ''

    const cleanup = streamRAG(
      query,
      (token) => {
        accumulated += token
        setMessages(prev =>
          prev.map(m => m.id === assistantMsg.id ? { ...m, text: accumulated } : m)
        )
      },
      (sources) => {
        setMessages(prev =>
          prev.map(m => m.id === assistantMsg.id ? { ...m, sources } : m)
        )
      },
      (error) => {
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantMsg.id
              ? { ...m, text: error || accumulated || '(no response)', streaming: false }
              : m
          )
        )
        setLoading(false)
      },
    )
    cleanupRef.current = cleanup
  }

  async function ingestFiles(files: FileList | File[]) {
    const list = Array.from(files)
    for (const file of list) {
      setIngestLog(l => [...l, `Ingesting ${file.name}…`])
      try {
        const res = await ingestFile(file)
        setIngestLog(l => [...l, formatIngestResult(file.name, res)])
        loadDocs()
      } catch (err: any) {
        const msg = err.message || 'Upload failed — is the server running?'
        setIngestLog(l => [...l, `✗ ${file.name}: ${msg}`])
        setMessages(prev => [...prev, { id: ++_msgId, role: 'assistant', text: `⚠ Upload failed: ${msg}` }])
      }
    }
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files
    if (!files?.length) return
    await ingestFiles(files)
    e.target.value = ''
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragging(false)
    if (e.dataTransfer.files.length) ingestFiles(e.dataTransfer.files)
  }

  async function handleURLIngest(url: string) {
    if (!url.trim()) return
    setIngestLog(l => [...l, `Ingesting ${url}…`])
    try {
      const res = await ingestURL(url)
      setIngestLog(l => [...l, formatIngestResult(res.source, res)])
      loadDocs()
    } catch (err: any) {
      setIngestLog(l => [...l, `✗ ${url}: ${err.message}`])
    }
  }

  async function handleDelete(docId: string, source: string) {
    setDeleteConfirm({ docId, source })
  }

  async function confirmDelete() {
    if (!deleteConfirm) return
    try {
      await deleteDoc(deleteConfirm.docId)
      setIngestLog(l => [...l, `✓ Deleted: ${deleteConfirm.source}`])
    } catch (err: any) {
      setIngestLog(l => [...l, `✗ Failed to delete: ${err.message}`])
    } finally {
      setDeleteConfirm(null)
      loadDocs()
    }
  }

  async function handleTTS(text: string) {
    try {
      const blob = await synthesiseTTS(text)
      const url  = URL.createObjectURL(blob)
      new Audio(url).play()
    } catch { /* TTS optional */ }
  }

  const lastSources = [...messages].reverse().find(m => m.role === 'assistant' && m.sources)?.sources ?? []

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <h1 className="logo">📖 OpenBook</h1>
        <section className="ingest-section">
          <h2>Add Materials</h2>
          <div
            className={`drop-zone ${dragging ? 'drop-zone-active' : ''}`}
            onDragOver={e => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <span className="drop-zone-title">Drop notes here</span>
            <span className="drop-zone-hint">PDF, TXT, or MD — or click to browse</span>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_TYPES}
              multiple
              onChange={handleFileUpload}
              hidden
            />
          </div>
          <p className="notes-folder-hint">
            Or copy files into the <code>notes/</code> folder while the server is running.
          </p>
          <URLInput onSubmit={handleURLIngest} />
        </section>

        {ingestLog.length > 0 && (
          <div className="ingest-log">
            {ingestLog.slice(-5).map((line, i) => <div key={i} className="log-line">{line}</div>)}
          </div>
        )}

        {dbWarning && (
          <div className="db-warning">
            <span className="warning-icon">⚠️</span>
            <p>{dbWarning}</p>
          </div>
        )}

        <section className="docs-section">
          <h2>Ingested Docs</h2>
          {docs.length === 0 && <p className="empty-hint">No documents yet. Drop a file above or add one to the notes/ folder.</p>}
          {docs.map(doc => (
            <div key={doc.doc_id} className="doc-item">
              <span className="doc-name" title={doc.source}>
                {doc.source.length > 30 ? '…' + doc.source.slice(-28) : doc.source}
              </span>
              <button className="delete-btn" onClick={() => handleDelete(doc.doc_id, doc.source)} aria-label="Delete">✕</button>
            </div>
          ))}
        </section>
      </aside>

      <main className="chat-main">
        <div className="messages">
          {messages.length === 0 && (
            <div className="welcome">
              <p>Ask anything about your uploaded notes.</p>
            </div>
          )}
          {messages.map(msg => (
            <div key={msg.id} className={`message ${msg.role}`}>
              <div className={`bubble ${msg.role === 'assistant' && !msg.text && !msg.streaming ? 'bubble-error' : ''}`}>
                {msg.text || (msg.streaming ? <span className="cursor">▍</span> : <span className="empty-msg">Waiting for response…</span>)}
                {msg.role === 'assistant' && !msg.streaming && msg.text && msg.text !== '(no response)' && (
                  <button className="tts-btn" onClick={() => handleTTS(msg.text)} aria-label="Read aloud">🔊</button>
                )}
              </div>
              {msg.latency_ms && <span className="meta">{msg.latency_ms}ms</span>}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <div className="input-row">
          <textarea
            className="query-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
            placeholder="Ask a question about your notes…"
            rows={2}
            disabled={loading}
          />
          <button className="send-btn" onClick={handleSend} disabled={loading || !input.trim()}>
            {loading ? '…' : '→'}
          </button>
        </div>
      </main>

      {lastSources.length > 0 && (
        <aside className="sources-panel">
          <h2>Sources</h2>
          {lastSources.map((src, i) => (
            <div key={i} className="source-card">
              <div className="source-meta">
                <span className="source-file">{src.source.split('/').pop()}</span>
                {src.page > 0 && <span className="source-page">p.{src.page + 1}</span>}
                <span className="source-score">{(1 - src.distance).toFixed(2)}</span>
              </div>
              <p className="source-text">{src.text}</p>
            </div>
          ))}
        </aside>
      )}

      {deleteConfirm && (
        <div className="modal-overlay" onClick={() => setDeleteConfirm(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>Delete document?</h3>
            <p className="modal-text">Are you sure you want to delete <strong>{deleteConfirm.source}</strong>?</p>
            <div className="modal-buttons">
              <button className="modal-cancel" onClick={() => setDeleteConfirm(null)}>Cancel</button>
              <button className="modal-confirm" onClick={confirmDelete}>Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function URLInput({ onSubmit }: { onSubmit: (url: string) => void }) {
  const [val, setVal] = useState('')
  return (
    <div className="url-input-row">
      <input
        type="url"
        placeholder="Paste URL or YouTube link"
        value={val}
        onChange={e => setVal(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') { onSubmit(val); setVal('') } }}
        className="url-input"
      />
      <button onClick={() => { onSubmit(val); setVal('') }} className="url-btn">Add</button>
    </div>
  )
}
