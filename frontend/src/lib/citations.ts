export type CitationSegment =
  | { kind: 'text'; value: string }
  | { kind: 'cite'; docId: number; page: number; raw: string }

const CITATION_RE = /\[\[(\d+):(\d+)\]\]/g

export function parseCitations(text: string): CitationSegment[] {
  if (text === '') return []

  const segments: CitationSegment[] = []
  let lastIndex = 0

  for (const match of text.matchAll(CITATION_RE)) {
    const index = match.index!
    if (index > lastIndex) {
      segments.push({ kind: 'text', value: text.slice(lastIndex, index) })
    }
    segments.push({
      kind: 'cite',
      docId: Number(match[1]),
      page: Number(match[2]),
      raw: match[0],
    })
    lastIndex = index + match[0].length
  }

  if (lastIndex < text.length) {
    segments.push({ kind: 'text', value: text.slice(lastIndex) })
  }

  if (segments.length === 0) {
    return [{ kind: 'text', value: text }]
  }

  return segments
}
