import { describe, expect, it } from 'vitest'
import { errorHelp } from './results'

describe('errorHelp', () => {
  it('offers an upload when YouTube blocks the server', () => {
    const help = errorHelp('YOUTUBE_BLOCKED')
    expect(help.action).toEqual({ label: 'Upload the file instead', to: '/app/new' })
    expect(help.title).toMatch(/YouTube/)
  })

  it('suggests re-exporting for unreadable files', () => {
    expect(errorHelp('CORRUPT_FILE').title).toMatch(/couldn't read/i)
    expect(errorHelp('DECODE_ERROR').action?.to).toBe('/app/new')
  })

  it('has a calm generic fallback for codes it does not know', () => {
    const help = errorHelp('SOMETHING_NEW')
    expect(help.title).toBe('The analysis failed')
    expect(help.action).toEqual({ label: 'Try another video', to: '/app/new' })
  })
})
