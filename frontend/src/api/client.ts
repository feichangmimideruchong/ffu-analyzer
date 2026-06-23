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

export type StreamHandlers = {
  onToken: (text: string) => void
  onStatus?: (status: string) => void
  onError?: (message: string) => void
}

export async function sendChatStream(
  message: string,
  history: ChatMessage[],
  handlers: StreamHandlers,
): Promise<void> {
  const res = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history }),
  })
  await checkResponse(res, 'sendChatStream failed')
  if (!res.body) throw new Error('sendChatStream failed: no response body')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split('\n\n')
    buffer = events.pop() ?? ''
    for (const evt of events) {
      const dataLine = evt.split('\n').find((line) => line.startsWith('data:'))
      if (!dataLine) continue
      let payload: { type: string; text?: string }
      try {
        payload = JSON.parse(dataLine.slice(5).trim())
      } catch {
        continue
      }
      if (payload.type === 'token' && payload.text) handlers.onToken(payload.text)
      else if (payload.type === 'status' && payload.text) handlers.onStatus?.(payload.text)
      else if (payload.type === 'error') handlers.onError?.(payload.text ?? 'Unknown error')
    }
  }
}

export type OverviewItem = {
  id: number
  document_id: number
  category: 'requirement' | 'deadline' | 'risk'
  text: string
  source_page: number
  normalized_date: string | null
  filename: string
}

export async function generateOverview(): Promise<number> {
  const res = await fetch('/api/overview/generate', { method: 'POST' })
  await checkResponse(res, 'generateOverview failed')
  const data = await res.json()
  return data.items as number
}

export async function fetchOverview(category?: string): Promise<OverviewItem[]> {
  const url = category ? `/api/overview?category=${encodeURIComponent(category)}` : '/api/overview'
  const res = await fetch(url)
  await checkResponse(res, 'fetchOverview failed')
  const data = await res.json()
  return data.items
}
