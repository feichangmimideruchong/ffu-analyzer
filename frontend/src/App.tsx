import {
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  useEffect,
  useRef,
  useState,
} from 'react'

import {
  ChatMessage,
  DocumentDetail,
  DocumentSummary,
  fetchGraph,
  fetchOverview,
  generateOverview,
  getDocument,
  getDocuments,
  Graph,
  OverviewItem,
  processFFU,
  sendChatStream,
} from './api/client'
import { DocumentList } from './components/DocumentList'
import { DocumentViewer } from './components/DocumentViewer'
import { GraphPanel } from './components/GraphPanel'
import { Message } from './components/Message'
import { OverviewPanel } from './components/OverviewPanel'

type AsidePanel = 'documents' | 'overview' | 'graph'

const clamp = (value: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, value))

function Resizer({ onResize, label }: { onResize: (dx: number) => void; label: string }) {
  const lastX = useRef(0)

  const handlePointerDown = (e: ReactPointerEvent) => {
    e.preventDefault()
    lastX.current = e.clientX
    const move = (ev: PointerEvent) => {
      onResize(ev.clientX - lastX.current)
      lastX.current = ev.clientX
    }
    const up = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }

  const handleKeyDown = (e: ReactKeyboardEvent) => {
    if (e.key === 'ArrowLeft') {
      e.preventDefault()
      onResize(-16)
    } else if (e.key === 'ArrowRight') {
      e.preventDefault()
      onResize(16)
    }
  }

  return (
    <div
      className="resizer"
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      tabIndex={0}
      onPointerDown={handlePointerDown}
      onKeyDown={handleKeyDown}
      style={ui.resizer}
    />
  )
}

const ui = {
  page: {
    margin: 0,
    height: '100vh',
    overflow: 'hidden',
    background: '#f7f7f8',
    color: '#1f2328',
    fontFamily: 'system-ui, sans-serif',
    display: 'flex',
    flexDirection: 'column' as const,
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: 16,
    padding: '12px 20px',
    borderBottom: '1px solid #e2e2e5',
    background: '#fff',
  },
  title: { margin: 0, fontSize: 18 },
  button: {
    padding: '8px 14px',
    border: '1px solid #c7c7cc',
    borderRadius: 8,
    background: '#fff',
    font: 'inherit',
    cursor: 'pointer',
  },
  status: { color: '#555', fontSize: 14 },
  main: {
    flex: 1,
    display: 'flex',
    flexDirection: 'row' as const,
    background: '#e2e2e5',
    minHeight: 0,
    overflow: 'hidden',
  },
  pane: {
    background: '#fff',
    display: 'flex',
    flexDirection: 'column' as const,
    minHeight: 0,
    minWidth: 0,
    overflow: 'hidden',
  },
  resizer: {
    flex: '0 0 6px',
    cursor: 'col-resize',
    alignSelf: 'stretch' as const,
  },
  paneHead: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottom: '1px solid #eee',
    paddingRight: 8,
  },
  iconButton: {
    border: '1px solid #c7c7cc',
    borderRadius: 6,
    background: '#fff',
    font: 'inherit',
    fontSize: 16,
    lineHeight: 1,
    cursor: 'pointer',
    padding: '2px 8px',
  },
  paneHeading: {
    margin: 0,
    padding: '10px 14px',
    fontSize: 13,
    fontWeight: 600,
    color: '#6b7280',
    textTransform: 'uppercase' as const,
    letterSpacing: 0.4,
    borderBottom: '1px solid #eee',
  },
  chatLog: { flex: 1, overflow: 'auto', padding: 14 },
  form: { display: 'flex', gap: 8, padding: 12, borderTop: '1px solid #eee' },
  field: {
    flex: 1,
    padding: '10px 12px',
    border: '1px solid #c7c7cc',
    borderRadius: 8,
    font: 'inherit',
  },
  scroll: { flex: 1, overflow: 'auto', padding: 14 },
}

export default function App() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [selectedDoc, setSelectedDoc] = useState<DocumentDetail | null>(null)
  const [docLoading, setDocLoading] = useState(false)
  const [activePage, setActivePage] = useState<number | null>(null)

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(false)
  const [status, setStatus] = useState('')
  const [panel, setPanel] = useState<AsidePanel>('documents')
  const [overviewItems, setOverviewItems] = useState<OverviewItem[]>([])
  const [overviewLoading, setOverviewLoading] = useState(false)
  const [graph, setGraph] = useState<Graph>({ nodes: [], edges: [] })
  const [graphLoading, setGraphLoading] = useState(false)

  const [chatOpen, setChatOpen] = useState(true)
  const [chatWidth, setChatWidth] = useState(420)
  const [asideWidth, setAsideWidth] = useState(280)

  const latestDocRequest = useRef<number | null>(null)

  useEffect(() => {
    getDocuments()
      .then(setDocuments)
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    if (panel === 'overview' && overviewItems.length === 0) {
      fetchOverview()
        .then(setOverviewItems)
        .catch(() => undefined)
    }
  }, [panel, overviewItems.length])

  useEffect(() => {
    if (panel === 'graph' && graph.edges.length === 0) {
      fetchGraph()
        .then(setGraph)
        .catch(() => undefined)
    }
  }, [panel, graph.edges.length])

  const handleProcess = async () => {
    setStatus('Processing documents…')
    try {
      const result = await processFFU()
      setDocuments(await getDocuments())
      setGraph(await fetchGraph())
      setStatus(`Indexed ${result.documents} document(s), ${result.chunks} chunk(s).`)
    } catch (e) {
      setStatus(`Error: ${e instanceof Error ? e.message : String(e)}`)
    }
  }

  const handleGenerateOverview = async () => {
    setOverviewLoading(true)
    setPanel('overview')
    setStatus('Extracting overview…')
    try {
      await generateOverview()
      setOverviewItems(await fetchOverview())
      setStatus('Overview updated.')
    } catch (e) {
      setStatus(`Error: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setOverviewLoading(false)
    }
  }

  const handleRefreshGraph = async () => {
    setGraphLoading(true)
    setStatus('Building reference graph…')
    try {
      setGraph(await fetchGraph())
      setStatus('Reference graph updated.')
    } catch (e) {
      setStatus(`Error: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setGraphLoading(false)
    }
  }

  const openDocument = async (id: number, page: number | null = null) => {
    latestDocRequest.current = id
    setSelectedId(id)
    setDocLoading(true)
    setActivePage(null)
    try {
      const detail = await getDocument(id)
      if (latestDocRequest.current !== id) return // a newer selection superseded this one
      setSelectedDoc(detail)
      setActivePage(page)
    } catch (e) {
      if (latestDocRequest.current !== id) return
      setStatus(`Error: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      if (latestDocRequest.current === id) setDocLoading(false)
    }
  }

  const handleSend = async (e: FormEvent) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || thinking) return
    const history = [...messages]
    setInput('')
    setThinking(true)
    // Seed the user message plus an empty assistant message that we grow as tokens arrive.
    setMessages([...history, { role: 'user', content: text }, { role: 'assistant', content: '' }])

    let answer = ''
    const setAssistant = (content: string) =>
      setMessages((m) => {
        const copy = [...m]
        copy[copy.length - 1] = { role: 'assistant', content }
        return copy
      })

    try {
      await sendChatStream(text, history, {
        onToken: (token) => {
          answer += token
          setAssistant(answer)
        },
        onStatus: (s) => setStatus(s),
        onError: (msg) => {
          answer += `${answer ? '\n\n' : ''}Error: ${msg}`
          setAssistant(answer)
        },
      })
    } catch (err) {
      setAssistant(`Error: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setThinking(false)
      setStatus('')
    }
  }

  return (
    <div style={ui.page}>
      <a href="#chat" className="skip-link">
        Skip to chat
      </a>
      <header style={ui.header}>
        <h1 style={ui.title}>FFU Analyzer</h1>
        <button
          type="button"
          aria-pressed={chatOpen}
          style={{ ...ui.button, background: chatOpen ? '#dbeafe' : '#fff' }}
          onClick={() => setChatOpen((v) => !v)}
        >
          {chatOpen ? 'Hide chat' : 'Show chat'}
        </button>
        <button type="button" style={ui.button} onClick={handleProcess}>
          Process FFU
        </button>
        <button
          type="button"
          aria-pressed={panel === 'overview'}
          style={{ ...ui.button, background: panel === 'overview' ? '#dbeafe' : '#fff' }}
          onClick={() => setPanel((p) => (p === 'overview' ? 'documents' : 'overview'))}
        >
          Overview
        </button>
        <button
          type="button"
          aria-pressed={panel === 'graph'}
          style={{ ...ui.button, background: panel === 'graph' ? '#dbeafe' : '#fff' }}
          onClick={() => setPanel((p) => (p === 'graph' ? 'documents' : 'graph'))}
        >
          Reference graph
        </button>
        <span role="status" aria-live="polite" style={ui.status}>
          {status}
        </span>
      </header>

      <main style={ui.main}>
        {chatOpen && (
          <section
            style={{ ...ui.pane, flex: `0 0 ${chatWidth}px` }}
            id="chat"
            aria-label="Chat"
            tabIndex={-1}
          >
            <div style={ui.paneHead}>
              <h2 style={{ ...ui.paneHeading, borderBottom: 'none', flex: 1 }}>Chat</h2>
              <button
                type="button"
                style={ui.iconButton}
                aria-label="Close chat"
                title="Close chat"
                onClick={() => setChatOpen(false)}
              >
                ×
              </button>
            </div>
          <div style={ui.chatLog}>
            {messages.map((message, i) => (
              <Message
                key={i}
                role={message.role}
                content={message.content}
                onCitation={(docId, page) => openDocument(docId, page)}
              />
            ))}
            {thinking && (
              <div aria-live="polite" style={{ color: '#4b5563' }}>
                Thinking…
              </div>
            )}
          </div>
          <form style={ui.form} onSubmit={handleSend}>
            <label htmlFor="chat-input" className="sr-only">
              Ask about the FFU documents
            </label>
            <input
              id="chat-input"
              style={ui.field}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about the FFU documents"
            />
            <button type="submit" style={ui.button} disabled={thinking}>
              Send
            </button>
          </form>
          </section>
        )}

        {chatOpen && (
          <Resizer
            label="Resize chat panel"
            onResize={(dx) => setChatWidth((w) => clamp(w + dx, 260, 760))}
          />
        )}

        <section style={{ ...ui.pane, flex: '1 1 0' }} aria-label="Document viewer">
          <h2 style={ui.paneHeading}>Source</h2>
          <div style={ui.scroll}>
            <DocumentViewer document={selectedDoc} loading={docLoading} activePage={activePage} />
          </div>
        </section>

        <Resizer
          label="Resize documents panel"
          onResize={(dx) => setAsideWidth((w) => clamp(w - dx, 200, 560))}
        />

        <aside
          style={{ ...ui.pane, flex: `0 0 ${asideWidth}px` }}
          aria-label={
            panel === 'overview' ? 'Overview' : panel === 'graph' ? 'Reference graph' : 'Document list'
          }
        >
          <h2 style={ui.paneHeading}>
            {panel === 'overview' ? 'Overview' : panel === 'graph' ? 'Reference graph' : 'Documents'}
          </h2>
          <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
            {panel === 'overview' ? (
              <OverviewPanel
                items={overviewItems}
                loading={overviewLoading}
                onGenerate={handleGenerateOverview}
                onOpenSource={(docId, page) => {
                  setPanel('documents')
                  openDocument(docId, page)
                }}
              />
            ) : panel === 'graph' ? (
              <GraphPanel
                graph={graph}
                selectedId={selectedId}
                loading={graphLoading}
                onRefresh={handleRefreshGraph}
                onSelectNode={(docId) => openDocument(docId)}
              />
            ) : (
              <div style={ui.scroll}>
                <DocumentList documents={documents} selectedId={selectedId} onSelect={openDocument} />
              </div>
            )}
          </div>
        </aside>
      </main>
    </div>
  )
}
