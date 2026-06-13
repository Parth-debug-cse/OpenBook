const BASE = '/api'

export interface Source {
  source: string
  page: number
  text: string
  distance: number
}

export interface QueryResult {
  answer: string
  sources: Source[]
  latency_ms: number
  prompt_tokens: number
}

export interface Doc {
  doc_id: string
  source: string
}

export interface DocsResponse {
  docs: Doc[]
  vector_dim: number
  row_count: number
  warning?: string
}

export async function queryRAG(query: string, topK = 5): Promise<QueryResult> {
  const res = await fetch(`${BASE}/query`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ query, top_k: topK }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export function streamRAG(
  query: string,
  onToken: (token: string) => void,
  onSources: (sources: Source[]) => void,
  onDone: (error?: string) => void,
  topK = 5,
): () => void {
  const url = `${BASE}/stream?query=${encodeURIComponent(query)}&top_k=${topK}`
  const es  = new EventSource(url)
  let isDone = false

  es.onmessage = (e) => {
    if (isDone) return
    if (e.data === '[DONE]') {
      isDone = true
      es.close()
      onDone()
      return
    }
    try {
      const parsed = JSON.parse(e.data)
      if (parsed.type === 'token')   onToken(parsed.text)
      if (parsed.type === 'sources') onSources(parsed.sources)
      if (parsed.type === 'error') {
        isDone = true
        onDone(parsed.text)
        return
      }
    } catch { /* ignore malformed chunks */ }
  }

  es.onerror = () => {
    if (!isDone) {
      isDone = true
      es.close()
      onDone('Connection error. Check server logs.')
    }
  }

  return () => {
    isDone = true
    es.close()
  }
}

export async function ingestFile(file: File): Promise<{
  chunks: number
  latency_ms: number
  status: string
  detail: string
  source: string
}> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/ingest/file`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/** @deprecated use ingestFile */
export const ingestPDF = ingestFile

export async function ingestURL(url: string): Promise<{
  chunks: number
  latency_ms: number
  source: string
  status: string
  detail: string
}> {
  const res = await fetch(`${BASE}/ingest/url`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ url }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function listDocs(): Promise<DocsResponse> {
  const res = await fetch(`${BASE}/docs`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function deleteDoc(docId: string): Promise<void> {
  const res = await fetch(`${BASE}/docs/${docId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await res.text())
}

export async function synthesiseTTS(text: string): Promise<Blob> {
  const res = await fetch(`${BASE}/tts`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ text }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.blob()
}
