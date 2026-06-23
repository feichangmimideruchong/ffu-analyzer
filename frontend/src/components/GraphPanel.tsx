import { useMemo } from 'react'

import { Graph, GraphNode } from '../api/client'

type Props = {
  graph: Graph
  selectedId: number | null
  loading: boolean
  onRefresh: () => void
  onSelectNode: (docId: number) => void
}

const SIZE = 340
const CENTER = SIZE / 2
const RADIUS = SIZE / 2 - 54
const NODE_R = 16

const KIND_COLOR: Record<string, string> = {
  base: '#2563eb',
  revision: '#d97706',
  amendment: '#dc2626',
}

function nodeColor(kind: string | null): string {
  return (kind && KIND_COLOR[kind]) || '#6b7280'
}

function shortLabel(node: GraphNode): string {
  return node.doc_code || node.filename.slice(0, 6)
}

export function GraphPanel({ graph, selectedId, loading, onRefresh, onSelectNode }: Props) {
  const { nodes, edges } = graph

  const positions = useMemo(() => {
    const map = new Map<number, { x: number; y: number }>()
    const n = nodes.length
    nodes.forEach((node, i) => {
      const angle = n > 0 ? (i / n) * 2 * Math.PI - Math.PI / 2 : 0
      map.set(node.id, {
        x: CENTER + RADIUS * Math.cos(angle),
        y: CENTER + RADIUS * Math.sin(angle),
      })
    })
    return map
  }, [nodes])

  const connected = useMemo(() => {
    const set = new Set<number>()
    if (selectedId == null) return set
    for (const e of edges) {
      if (e.source === selectedId) set.add(e.target)
      if (e.target === selectedId) set.add(e.source)
    }
    return set
  }, [edges, selectedId])

  const selectedNode = nodes.find((n) => n.id === selectedId) || null
  const outgoing = edges.filter((e) => e.source === selectedId)
  const incoming = edges.filter((e) => e.target === selectedId)
  const nameOf = (id: number) => nodes.find((n) => n.id === id)?.filename || `Document ${id}`

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px' }}>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          style={{
            padding: '6px 12px',
            border: '1px solid #c7c7cc',
            borderRadius: 8,
            background: '#fff',
            font: 'inherit',
            cursor: loading ? 'default' : 'pointer',
          }}
        >
          {loading ? 'Building…' : 'Rebuild graph'}
        </button>
        <span style={{ fontSize: 12, color: '#6b7280' }}>
          {nodes.length} docs · {edges.length} links
        </span>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '0 14px 14px' }}>
        {edges.length === 0 ? (
          <p style={{ color: '#6b7280', fontSize: 14 }}>
            No cross-document references found yet. Process the documents to build the graph.
          </p>
        ) : (
          <svg
            viewBox={`0 0 ${SIZE} ${SIZE}`}
            width="100%"
            aria-hidden="true"
            style={{ display: 'block', maxWidth: 380, margin: '0 auto' }}
          >
            <defs>
              <marker
                id="arrow"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#9ca3af" />
              </marker>
            </defs>
            {edges.map((e, i) => {
              const a = positions.get(e.source)
              const b = positions.get(e.target)
              if (!a || !b) return null
              const active = selectedId != null && (e.source === selectedId || e.target === selectedId)
              return (
                <line
                  key={i}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={active ? '#2563eb' : '#d1d5db'}
                  strokeWidth={active ? 2 : 1}
                  markerEnd="url(#arrow)"
                />
              )
            })}
            {nodes.map((node) => {
              const p = positions.get(node.id)
              if (!p) return null
              const isSelected = node.id === selectedId
              const isConnected = connected.has(node.id)
              const dim = selectedId != null && !isSelected && !isConnected
              return (
                <g
                  key={node.id}
                  transform={`translate(${p.x}, ${p.y})`}
                  onClick={() => onSelectNode(node.id)}
                  style={{ cursor: 'pointer', opacity: dim ? 0.45 : 1 }}
                >
                  <circle
                    r={NODE_R}
                    fill={nodeColor(node.doc_kind)}
                    stroke={isSelected ? '#1f2328' : '#fff'}
                    strokeWidth={isSelected ? 3 : 2}
                  />
                  <text
                    textAnchor="middle"
                    dy="0.35em"
                    fontSize="9"
                    fill="#fff"
                    style={{ pointerEvents: 'none', fontWeight: 600 }}
                  >
                    {shortLabel(node)}
                  </text>
                </g>
              )
            })}
          </svg>
        )}

        {nodes.length > 0 && (
          <div style={{ marginTop: 14 }}>
            <h3 style={{ fontSize: 12, color: '#6b7280', margin: '0 0 6px', fontWeight: 600 }}>
              Documents
            </h3>
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 4 }}>
              {nodes.map((node) => (
                <li key={node.id}>
                  <button
                    type="button"
                    aria-current={node.id === selectedId ? 'true' : undefined}
                    onClick={() => onSelectNode(node.id)}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '6px 8px',
                      border: '1px solid #e5e7eb',
                      borderRadius: 6,
                      background: node.id === selectedId ? '#dbeafe' : '#fff',
                      font: 'inherit',
                      fontSize: 13,
                      cursor: 'pointer',
                    }}
                  >
                    <span aria-hidden="true" style={{ color: nodeColor(node.doc_kind) }}>
                      ●{' '}
                    </span>
                    {node.filename}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div style={{ marginTop: 14 }}>
          <h3 style={{ fontSize: 13, color: '#374151', margin: '0 0 8px' }}>
            {selectedNode ? selectedNode.filename : 'Select a document'}
          </h3>
          {selectedNode ? (
            <>
              <ConnectionList
                title={`References (${outgoing.length})`}
                empty="This document references no others."
                items={outgoing.map((e) => ({
                  id: e.target,
                  name: nameOf(e.target),
                  labels: e.labels,
                }))}
                onSelect={onSelectNode}
              />
              <ConnectionList
                title={`Referenced by (${incoming.length})`}
                empty="No documents reference this one."
                items={incoming.map((e) => ({
                  id: e.source,
                  name: nameOf(e.source),
                  labels: e.labels,
                }))}
                onSelect={onSelectNode}
              />
            </>
          ) : (
            <p style={{ color: '#6b7280', fontSize: 13 }}>
              Click a node to see what it depends on and what depends on it.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

type ConnItem = { id: number; name: string; labels: string[] }

function ConnectionList({
  title,
  empty,
  items,
  onSelect,
}: {
  title: string
  empty: string
  items: ConnItem[]
  onSelect: (id: number) => void
}) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', marginBottom: 4 }}>{title}</div>
      {items.length === 0 ? (
        <div style={{ fontSize: 12, color: '#6b7280' }}>{empty}</div>
      ) : (
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 4 }}>
          {items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => onSelect(item.id)}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  padding: '6px 8px',
                  border: '1px solid #e5e7eb',
                  borderRadius: 6,
                  background: '#fff',
                  font: 'inherit',
                  fontSize: 13,
                  cursor: 'pointer',
                }}
              >
                {item.name}
                {item.labels.length > 0 && (
                  <span style={{ color: '#6b7280', fontSize: 11 }}> · {item.labels.join(', ')}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
