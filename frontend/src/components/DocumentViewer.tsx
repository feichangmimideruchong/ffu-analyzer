import { useEffect, useRef, useState } from 'react'
import type { DocumentDetail } from '../api/client'

export type DocumentViewerProps = {
  document: DocumentDetail | null
  loading?: boolean
  activePage?: number | null
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
                <div style={{ fontWeight: 'bold', marginBottom: '0.25rem' }}>{chunk.heading}</div>
              ) : null}
              <div style={{ whiteSpace: 'pre-wrap' }}>{chunk.text}</div>
            </div>
          ))}
        </section>
      ))}
    </article>
  )
}
