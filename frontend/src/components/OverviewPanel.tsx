import { useState } from 'react'

import type { OverviewItem } from '../api/client'

type OverviewPanelProps = {
  items: OverviewItem[]
  loading: boolean
  onGenerate: () => void
  onOpenSource: (docId: number, page: number) => void
}

const FILTERS = ['all', 'requirement', 'deadline', 'risk'] as const

export function OverviewPanel(props: OverviewPanelProps) {
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>('all')
  const visible =
    filter === 'all' ? props.items : props.items.filter((i) => i.category === filter)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', gap: 8, padding: '8px 12px', borderBottom: '1px solid #eee' }}>
        <button type="button" onClick={props.onGenerate} disabled={props.loading} style={btn}>
          {props.loading ? 'Extracting…' : 'Generate overview'}
        </button>
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            aria-pressed={filter === f}
            onClick={() => setFilter(f)}
            style={{ ...btn, background: filter === f ? '#dbeafe' : '#fff' }}
          >
            {f}
          </button>
        ))}
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: 12 }}>
        {visible.length === 0 ? (
          <p style={{ color: '#888' }}>No overview items yet. Run Generate overview after processing.</p>
        ) : (
          <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
            {visible.map((item) => (
              <li key={item.id} style={{ marginBottom: 12, padding: 10, background: '#f9fafb', borderRadius: 8 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: categoryColor(item.category), textTransform: 'uppercase' }}>
                  {item.category}
                  {item.normalized_date ? ` · ${item.normalized_date}` : ''}
                </div>
                <div style={{ margin: '6px 0', whiteSpace: 'pre-wrap' }}>{item.text}</div>
                <button
                  type="button"
                  style={{ ...btn, fontSize: 12, padding: '4px 8px' }}
                  onClick={() => props.onOpenSource(item.document_id, item.source_page)}
                >
                  {item.filename} p.{item.source_page}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

const btn = {
  padding: '6px 10px',
  border: '1px solid #c7c7cc',
  borderRadius: 6,
  background: '#fff',
  font: 'inherit',
  cursor: 'pointer',
} as const

function categoryColor(cat: string) {
  if (cat === 'deadline') return '#b45309'
  if (cat === 'risk') return '#b91c1c'
  return '#1d4ed8'
}
