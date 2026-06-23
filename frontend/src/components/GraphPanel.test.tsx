import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe } from 'jest-axe'
import { describe, expect, it, vi } from 'vitest'

import type { Graph } from '../api/client'
import { GraphPanel } from './GraphPanel'

const graph: Graph = {
  nodes: [
    { id: 1, filename: '09.1 AF.pdf', doc_code: '09.1', doc_kind: 'base' },
    { id: 2, filename: '10.1 Mängd.pdf', doc_code: '10.1', doc_kind: 'revision' },
    { id: 3, filename: '13.1 Anbud.xlsx', doc_code: '13.1', doc_kind: 'base' },
  ],
  edges: [
    { source: 1, target: 2, count: 1, page: 14, labels: ['10.1'] },
    { source: 1, target: 3, count: 1, page: 8, labels: ['13.1'] },
  ],
}

describe('GraphPanel', () => {
  it('shows the docs/links summary', () => {
    render(<GraphPanel graph={graph} selectedId={null} loading={false} onRefresh={() => {}} onSelectNode={() => {}} />)
    expect(screen.getByText(/3 docs/)).toBeInTheDocument()
    expect(screen.getByText(/2 links/)).toBeInTheDocument()
  })

  it('renders an accessible node list and selects a node', async () => {
    const onSelectNode = vi.fn()
    render(<GraphPanel graph={graph} selectedId={null} loading={false} onRefresh={() => {}} onSelectNode={onSelectNode} />)
    await userEvent.click(screen.getByRole('button', { name: /09\.1 AF\.pdf/i }))
    expect(onSelectNode).toHaveBeenCalledWith(1)
  })

  it('shows outgoing references for the selected node', () => {
    render(<GraphPanel graph={graph} selectedId={1} loading={false} onRefresh={() => {}} onSelectNode={() => {}} />)
    expect(screen.getByText(/References \(2\)/)).toBeInTheDocument()
    expect(screen.getByText(/Referenced by \(0\)/)).toBeInTheDocument()
  })

  it('shows empty state when there are no edges', () => {
    render(
      <GraphPanel
        graph={{ nodes: [], edges: [] }}
        selectedId={null}
        loading={false}
        onRefresh={() => {}}
        onSelectNode={() => {}}
      />,
    )
    expect(screen.getByText(/no cross-document references/i)).toBeInTheDocument()
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <GraphPanel graph={graph} selectedId={1} loading={false} onRefresh={() => {}} onSelectNode={() => {}} />,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
