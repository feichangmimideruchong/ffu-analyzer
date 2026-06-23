export type DocumentSummary = {
  id: number
  filename: string
  doc_code: string | null
  is_revision: number
  revision_label: string | null
}

export type DocumentChunk = {
  page: number
  heading: string | null
  text: string
}

export type DocumentDetail = {
  id: number
  filename: string
  doc_code: string | null
  doc_number: string | null
  is_revision: number
  revision_label: string | null
  content: string
  chunks: DocumentChunk[]
}

export type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
}

async function checkResponse(res: Response, context: string): Promise<void> {
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`${context}: ${res.status} ${res.statusText}${body ? ` — ${body}` : ''}`)
  }
}

export async function processFFU(): Promise<{
  status: string
  count: number
  documents: number
  chunks: number
}> {
  const res = await fetch('/api/process', { method: 'POST' })
  await checkResponse(res, 'processFFU failed')
  return res.json()
}

export async function getDocuments(): Promise<DocumentSummary[]> {
  const res = await fetch('/api/documents')
  await checkResponse(res, 'getDocuments failed')
  const data = await res.json()
  return data.documents
}

export async function getDocument(id: number): Promise<DocumentDetail> {
  const res = await fetch(`/api/document/${id}`)
  await checkResponse(res, 'getDocument failed')
  return res.json()
}

export async function sendChat(message: string, history: ChatMessage[]): Promise<string> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history }),
  })
  await checkResponse(res, 'sendChat failed')
  const data = await res.json()
  return data.response
}
