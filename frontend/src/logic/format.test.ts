import { describe, expect, it } from 'vitest'
import { formatBytes, formatDateTime, formatDuration } from './format'

describe('formatBytes', () => {
  it('uses the largest sensible unit with one decimal', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(999)).toBe('999 B')
    expect(formatBytes(1536)).toBe('1.5 KB')
    expect(formatBytes(48_234_496)).toBe('46.0 MB')
    expect(formatBytes(100 * 1024 * 1024)).toBe('100.0 MB')
  })

  it('shows a dash when the size is unknown', () => {
    expect(formatBytes(null)).toBe('—')
  })
})

describe('formatDuration', () => {
  it('is m:ss, rounded to the nearest second', () => {
    expect(formatDuration(0)).toBe('0:00')
    expect(formatDuration(9.4)).toBe('0:09')
    expect(formatDuration(59.6)).toBe('1:00')
    expect(formatDuration(125)).toBe('2:05')
  })

  it('shows a dash when unknown', () => {
    expect(formatDuration(null)).toBe('—')
    expect(formatDuration(Number.NaN)).toBe('—')
  })
})

describe('formatDateTime', () => {
  it('formats in the viewer locale and time zone', () => {
    const text = formatDateTime('2026-10-02T08:30:00Z', 'en-GB', 'Asia/Kolkata')
    expect(text).toContain('2 Oct 2026')
    expect(text).toContain('14:00')
  })
})
