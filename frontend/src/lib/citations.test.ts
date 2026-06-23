import { describe, expect, it } from 'vitest'

import { parseCitations } from './citations'

describe('parseCitations', () => {
  it('returns empty array for empty string', () => {
    expect(parseCitations('')).toEqual([])
  })

  it('returns a single text segment when there are no citations', () => {
    expect(parseCitations('plain text')).toEqual([{ kind: 'text', value: 'plain text' }])
  })

  it('parses a single citation token', () => {
    const segments = parseCitations('See [[3:5]] for details')
    expect(segments).toEqual([
      { kind: 'text', value: 'See ' },
      { kind: 'cite', docId: 3, page: 5, raw: '[[3:5]]' },
      { kind: 'text', value: ' for details' },
    ])
  })

  it('parses multiple citations', () => {
    const segments = parseCitations('[[1:2]] and [[10:20]]')
    const cites = segments.filter((s) => s.kind === 'cite')
    expect(cites).toHaveLength(2)
    expect(cites[0]).toMatchObject({ docId: 1, page: 2 })
    expect(cites[1]).toMatchObject({ docId: 10, page: 20 })
  })

  it('handles a citation at the very start', () => {
    const segments = parseCitations('[[1:1]] start')
    expect(segments[0]).toMatchObject({ kind: 'cite', docId: 1, page: 1 })
  })
})
