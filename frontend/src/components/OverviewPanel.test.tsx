import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe } from 'jest-axe'
import { describe, expect, it, vi } from 'vitest'

import type { OverviewItem } from '../api/client'
import { OverviewPanel } from './OverviewPanel'

const items: OverviewItem[] = [
  {
    id: 1,
    document_id: 1,
    category: 'requirement',
    text: 'A CV must be attached',
    source_page: 2,
    normalized_date: null,
    filename: '13.1 Anbud.xlsx',
  },
  {
    id: 2,
    document_id: 2,
    category: 'deadline',
    text: 'Inform 10 days in advance',
    source_page: 6,
    normalized_date: '2025-05-21',
    filename: '10.1 Mängd.pdf',
  },
]

describe('OverviewPanel', () => {
  it('renders all items by default', () => {
    render(<OverviewPanel items={items} loading={false} onGenerate={() => {}} onOpenSource={() => {}} />)
    expect(screen.getByText('A CV must be attached')).toBeInTheDocument()
    expect(screen.getByText('Inform 10 days in advance')).toBeInTheDocument()
  })

  it('filters by category', async () => {
    render(<OverviewPanel items={items} loading={false} onGenerate={() => {}} onOpenSource={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: 'deadline' }))
    expect(screen.queryByText('A CV must be attached')).not.toBeInTheDocument()
    expect(screen.getByText('Inform 10 days in advance')).toBeInTheDocument()
  })

  it('opens the source for an item', async () => {
    const onOpenSource = vi.fn()
    render(
      <OverviewPanel items={items} loading={false} onGenerate={() => {}} onOpenSource={onOpenSource} />,
    )
    await userEvent.click(screen.getByRole('button', { name: /13\.1 Anbud\.xlsx p\.2/i }))
    expect(onOpenSource).toHaveBeenCalledWith(1, 2)
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <OverviewPanel items={items} loading={false} onGenerate={() => {}} onOpenSource={() => {}} />,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
