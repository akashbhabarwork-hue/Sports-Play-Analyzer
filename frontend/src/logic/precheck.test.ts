import { describe, expect, it } from 'vitest'
import { MAX_BYTES, MAX_SECONDS, checkDuration, checkFile, checkUrl } from './precheck'

const file = (name: string, size: number, type = 'video/mp4') => ({ name, size, type })

describe('checkFile', () => {
  it('accepts a normal clip', () => {
    expect(checkFile(file('match.mp4', 5_000_000))).toBeNull()
  })

  it('rejects files over 100 MB before uploading them', () => {
    expect(checkFile(file('big.mp4', MAX_BYTES + 1))).toMatch(/larger than 100 MB/)
    expect(checkFile(file('edge.mp4', MAX_BYTES))).toBeNull()
  })

  it('rejects empty files', () => {
    expect(checkFile(file('empty.mp4', 0))).toMatch(/empty/)
  })

  it('rejects obvious non-videos but lets unknown types through to the server', () => {
    expect(checkFile(file('notes.pdf', 1000, 'application/pdf'))).toMatch(/not a video/)
    // Browsers often report '' for .mkv/.avi: the server sniffs the bytes, so allow it.
    expect(checkFile(file('clip.mkv', 1000, ''))).toBeNull()
  })
})

describe('checkDuration', () => {
  it('allows up to 60 s (plus container rounding) and rejects longer clips', () => {
    expect(checkDuration(MAX_SECONDS)).toBeNull()
    expect(checkDuration(60.4)).toBeNull()
    expect(checkDuration(61)).toMatch(/61 s long; the limit is 60 s/)
  })

  it('does not block when the browser cannot read the duration', () => {
    expect(checkDuration(Number.NaN)).toBeNull()
    expect(checkDuration(Infinity)).toBeNull()
  })
})

describe('checkUrl', () => {
  it('needs something that looks like a link', () => {
    expect(checkUrl('')).toMatch(/Paste a YouTube link/)
    expect(checkUrl('not a url')).toMatch(/full link/)
  })

  it('leaves the YouTube rules to the server', () => {
    expect(checkUrl('https://youtu.be/dQw4w9WgXcQ')).toBeNull()
    expect(checkUrl('https://example.com/video')).toBeNull() // server answers URL_NOT_ALLOWED
  })
})
