import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe } from 'jest-axe'
import { describe, expect, it, vi } from 'vitest'

import type { DocumentSummary } from '../api/client'
import { DocumentList } from './DocumentList'

const docs: DocumentSummary[] = [
  { id: 1, filename: '09.1 AF.pdf', doc_code: '09.1', is_revision: 0, revision_label: null },
  { id: 2, filename: '10.1 Mängd.pdf', doc_code: '10.1', is_revision: 1, revision_label: '2025-05-13' },
]

describe('DocumentList', () => {
  it('renders all documents', () => {
    render(<DocumentList documents={docs} selectedId={null} onSelect={() => {}} />)
    expect(screen.getByText('09.1 AF.pdf')).toBeInTheDocument()
    expect(screen.getByText('10.1 Mängd.pdf')).toBeInTheDocument()
  })

  it('shows a revision badge for revisions', () => {
    render(<DocumentList documents={docs} selectedId={null} onSelect={() => {}} />)
    expect(screen.getByText(/rev 2025-05-13/i)).toBeInTheDocument()
  })

  it('marks the selected document with aria-current', () => {
    render(<DocumentList documents={docs} selectedId={2} onSelect={() => {}} />)
    const selected = screen.getByRole('button', { name: /10\.1 Mängd/i })
    expect(selected).toHaveAttribute('aria-current', 'true')
  })

  it('calls onSelect with the document id', async () => {
    const onSelect = vi.fn()
    render(<DocumentList documents={docs} selectedId={null} onSelect={onSelect} />)
    await userEvent.click(screen.getByRole('button', { name: /09\.1 AF/i }))
    expect(onSelect).toHaveBeenCalledWith(1)
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <DocumentList documents={docs} selectedId={1} onSelect={() => {}} />,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
