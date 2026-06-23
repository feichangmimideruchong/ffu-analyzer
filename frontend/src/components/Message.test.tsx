import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe } from 'jest-axe'
import { describe, expect, it, vi } from 'vitest'

import { Message } from './Message'

describe('Message', () => {
  it('renders plain user content', () => {
    render(<Message role="user" content="hello" />)
    expect(screen.getByText('hello')).toBeInTheDocument()
  })

  it('renders citations as buttons and fires onCitation with docId/page', async () => {
    const onCitation = vi.fn()
    render(<Message role="assistant" content="See [[3:5]] now" onCitation={onCitation} />)
    const button = screen.getByRole('button', { name: /open document 3 page 5/i })
    await userEvent.click(button)
    expect(onCitation).toHaveBeenCalledWith(3, 5)
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <Message role="assistant" content="Answer [[1:2]] grounded" onCitation={() => {}} />,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
