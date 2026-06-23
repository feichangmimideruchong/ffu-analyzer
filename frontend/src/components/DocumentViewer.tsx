import { useEffect, useRef, useState } from 'react'
import type { DocumentDetail } from '../api/client'

export type DocumentViewerProps = {
  document: DocumentDetail | null
  loading?: boolean
  activePage?: number | null
}

// Renders the lightweight Markdown that pymupdf4llm produces (headings, bold,
// <br> line breaks) instead of showing the raw ##/** markers as literal text.
function renderInline(text: string) {
  return text.split(/\*\*/).map((part, i) =>
    i % 2 === 1 ? <strong key={i}>{part}</strong> : <span key={i}>{part}</span>,
  )
}

function MarkdownText({ text }: { text: string }) {
  const lines = text.replace(/<br\s*\/?>/gi, '\n').split('\n')
  return (
    <>
      {lines.map((line, i) => {
        const heading = /^(#{1,6})\s+(.*)$/.exec(line)
        if (heading) {
          const level = heading[1].length
          const content = heading[2].replace(/\*\*/g, '').trim()
          return (
            <div
              key={i}
              style={{
                fontWeight: 700,
                fontSize: level <= 2 ? '1rem' : '0.9rem',
                margin: '0.6rem 0 0.2rem',
              }}
            >
              {content}
            </div>
          )
        }
        if (line.trim() === '') return <div key={i} style={{ height: '0.5rem' }} />
        return (
          <div key={i} style={{ whiteSpace: 'pre-wrap' }}>
            {renderInline(line)}
          </div>
        )
      })}
    </>
  )
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
