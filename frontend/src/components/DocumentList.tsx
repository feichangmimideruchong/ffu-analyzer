import type { DocumentSummary } from '../api/client'

export type DocumentListProps = {
  documents: DocumentSummary[]
  selectedId: number | null
  onSelect: (id: number) => void
}

export function DocumentList(props: DocumentListProps) {
  return (
    <nav aria-label="Documents">
      <ul
        style={{
          listStyle: 'none',
          margin: 0,
          padding: 0,
        }}
      >
        {props.documents.map((doc) => {
          const isSelected = doc.id === props.selectedId
          return (
            <li key={doc.id} style={{ marginBottom: '0.25rem' }}>
              <button
                type="button"
                aria-current={isSelected ? 'true' : undefined}
                onClick={() => props.onSelect(doc.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  width: '100%',
                  padding: '0.5rem 0.75rem',
                  border: 'none',
                  borderRadius: '0.375rem',
                  backgroundColor: isSelected ? '#dbeafe' : 'transparent',
                  cursor: 'pointer',
                  textAlign: 'left',
                  font: 'inherit',
                }}
              >
                <span>{doc.filename}</span>
                {doc.is_revision ? (
                  <span
                    style={{
                      fontSize: '0.75rem',
                      padding: '0.125rem 0.375rem',
                      borderRadius: '0.25rem',
                      backgroundColor: '#f3f4f6',
                      color: '#6b7280',
                    }}
                  >
                    rev{doc.revision_label ? ` ${doc.revision_label}` : ''}
                  </span>
                ) : null}
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
