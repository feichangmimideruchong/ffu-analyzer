import { type ReactNode, useEffect, useRef, useState } from 'react'
import type { DocumentDetail } from '../api/client'

export type DocumentViewerProps = {
  document: DocumentDetail | null
  loading?: boolean
  activePage?: number | null
}

// Renders the lightweight Markdown that pymupdf4llm produces (headings, bold,
// italics, tables, <br> line breaks) instead of showing raw markers as text.

// Italic: _text_ / *text* only at word boundaries, so codes like "Eka 3_3" are left alone.
function renderItalic(text: string, keyBase: string) {
  const re = /(?<![\w])([_*])([^\n]+?)\1(?![\w])/g
  const nodes: ReactNode[] = []
  let last = 0
  let n = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push(<span key={`${keyBase}t${n}`}>{text.slice(last, m.index)}</span>)
    nodes.push(<em key={`${keyBase}e${n}`}>{m[2]}</em>)
    last = m.index + m[0].length
    n += 1
  }
  if (last < text.length) nodes.push(<span key={`${keyBase}t${n}`}>{text.slice(last)}</span>)
  return nodes
}

function renderInline(text: string) {
  return text.split(/\*\*/).map((part, i) =>
    i % 2 === 1 ? (
      <strong key={i}>{part}</strong>
    ) : (
      <span key={i}>{renderItalic(part, String(i))}</span>
    ),
  )
}

const isTableLine = (line: string) => line.includes('|') && line.trim() !== ''
const isSeparatorRow = (line: string) => /^[\s|:-]*-[\s|:-]*$/.test(line)

function splitCells(line: string): string[] {
  const cells = line.split('|').map((c) => c.trim())
  // Markdown rows are wrapped in pipes (|a|b|), producing empty leading/trailing cells.
  if (cells.length && cells[0] === '') cells.shift()
  if (cells.length && cells[cells.length - 1] === '') cells.pop()
  return cells
}

function Table({ rows }: { rows: string[][] }) {
  const cols = Math.max(...rows.map((r) => r.length), 1)
  return (
    <div style={{ overflowX: 'auto', margin: '0.4rem 0' }}>
      <table style={{ borderCollapse: 'collapse', fontSize: '0.85rem', width: '100%' }}>
        <tbody>
          {rows.map((row, r) => (
            <tr key={r}>
              {Array.from({ length: cols }).map((_, c) => (
                <td
                  key={c}
                  style={{
                    border: '1px solid #e5e7eb',
                    padding: '3px 6px',
                    verticalAlign: 'top',
                  }}
                >
                  {renderInline(row[c] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function MarkdownText({ text }: { text: string }) {
  const lines = text.replace(/<br\s*\/?>/gi, '\n').split('\n')
  const blocks: ReactNode[] = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]

    if (isTableLine(line)) {
      const rows: string[][] = []
      while (i < lines.length && isTableLine(lines[i])) {
        if (!isSeparatorRow(lines[i])) rows.push(splitCells(lines[i]))
        i += 1
      }
      if (rows.length) blocks.push(<Table key={`tbl${i}`} rows={rows} />)
      continue
    }

    const heading = /^(#{1,6})\s+(.*)$/.exec(line)
    if (heading) {
      const level = heading[1].length
      const content = heading[2].replace(/\*\*/g, '').trim()
      blocks.push(
        <div
          key={i}
          style={{ fontWeight: 700, fontSize: level <= 2 ? '1rem' : '0.9rem', margin: '0.6rem 0 0.2rem' }}
        >
          {content}
        </div>,
      )
    } else if (line.trim() === '') {
      blocks.push(<div key={i} style={{ height: '0.5rem' }} />)
    } else {
      blocks.push(
        <div key={i} style={{ whiteSpace: 'pre-wrap' }}>
          {renderInline(line)}
        </div>,
      )
    }
    i += 1
  }
  return <>{blocks}</>
}

export function DocumentViewer(props: DocumentViewerProps) {
  const pageRefs = useRef<Map<number, HTMLElement>>(new Map())
  const [highlightedPage, setHighlightedPage] = useState<number | null>(null)

  useEffect(() => {
    if (props.activePage == null || props.document == null) return

    const element = pageRefs.current.get(props.activePage)
    if (!element) return

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    element.scrollIntoView({ behavior: prefersReducedMotion ? 'auto' : 'smooth', block: 'start' })
    setHighlightedPage(props.activePage)

    const timeout = setTimeout(() => setHighlightedPage(null), 1500)
    return () => clearTimeout(timeout)
  }, [props.activePage, props.document])

  if (props.loading) {
    return <div>Loading document…</div>
  }

  if (props.document == null) {
    return (
      <div style={{ color: '#4b5563' }}>
        Select a document or click a citation to view its source.
      </div>
    )
  }

  const document = props.document

  const pageGroups = new Map<number, typeof document.chunks>()
  for (const chunk of document.chunks) {
    const group = pageGroups.get(chunk.page) ?? []
    group.push(chunk)
    pageGroups.set(chunk.page, group)
  }
  const sortedPages = Array.from(pageGroups.keys()).sort((a, b) => a - b)

  return (
    <article>
      <header style={{ marginBottom: '1rem' }}>
        <h3 style={{ margin: 0, display: 'inline' }}>{document.filename}</h3>
        {document.is_revision ? (
          <span
            style={{
              marginLeft: '0.5rem',
              fontSize: '0.75rem',
              padding: '0.125rem 0.375rem',
              borderRadius: '0.25rem',
              backgroundColor: '#f3f4f6',
              color: '#6b7280',
            }}
          >
            revision{document.revision_label ? ` ${document.revision_label}` : ''}
          </span>
        ) : null}
      </header>

      {sortedPages.map((page) => (
        <section
          key={page}
          id={`page-${page}`}
          ref={(el) => {
            if (el) {
              pageRefs.current.set(page, el)
            } else {
              pageRefs.current.delete(page)
            }
          }}
          style={{
            marginBottom: '1.5rem',
            padding: '0.75rem',
            borderRadius: '0.375rem',
            backgroundColor: highlightedPage === page ? '#fef9c3' : 'transparent',
            transition: 'background-color 0.3s ease',
          }}
        >
          <div
            style={{
              fontSize: '0.75rem',
              fontWeight: 600,
              color: '#6b7280',
              marginBottom: '0.5rem',
            }}
          >
            Page {page}
          </div>
          {pageGroups.get(page)!.map((chunk, index) => (
            <div key={index} style={{ marginBottom: '0.75rem' }}>
              {chunk.heading ? (
                <div style={{ fontWeight: 'bold', marginBottom: '0.25rem' }}>
                  {chunk.heading.replace(/\*\*/g, '')}
                </div>
              ) : null}
              <MarkdownText text={chunk.text} />
            </div>
          ))}
        </section>
      ))}
    </article>
  )
}
