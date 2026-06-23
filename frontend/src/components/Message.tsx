import { parseCitations } from '../lib/citations'

export type MessageProps = {
  role: 'user' | 'assistant'
  content: string
  onCitation?: (docId: number, page: number) => void
}

export function Message(props: MessageProps) {
  const isUser = props.role === 'user'

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        marginBottom: '0.75rem',
      }}
    >
      <div
        style={{
          maxWidth: '85%',
          padding: '0.625rem 0.875rem',
          borderRadius: '0.75rem',
          backgroundColor: isUser ? '#f0f0f0' : '#e8e8e8',
          whiteSpace: 'pre-wrap',
          textAlign: isUser ? 'right' : 'left',
        }}
      >
        {isUser ? (
          props.content
        ) : (
          <>
            {parseCitations(props.content).map((segment, index) =>
              segment.kind === 'text' ? (
                <span key={index}>{segment.value}</span>
              ) : (
                <button
                  key={index}
                  type="button"
                  aria-label={`Open document ${segment.docId} page ${segment.page}`}
                  onClick={() => props.onCitation?.(segment.docId, segment.page)}
                  style={{
                    display: 'inline',
                    padding: '0 0.25rem',
                    margin: '0 0.125rem',
                    border: 'none',
                    background: 'none',
                    color: '#1d4ed8',
                    cursor: 'pointer',
                    font: 'inherit',
                    textDecoration: 'underline',
                    verticalAlign: 'baseline',
                  }}
                >
                  {segment.raw}
                </button>
              ),
            )}
          </>
        )}
      </div>
    </div>
  )
}
