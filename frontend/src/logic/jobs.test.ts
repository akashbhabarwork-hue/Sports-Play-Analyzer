import { describe, expect, it } from 'vitest'
import type { JobSummary } from '../types'
import { anyActive, isActive, stageLabel, statusLabel } from './jobs'

const job = (status: JobSummary['status']) => ({ status }) as JobSummary

describe('job status helpers', () => {
  it('treats queued and processing as active (worth polling)', () => {
    expect(isActive(job('queued'))).toBe(true)
    expect(isActive(job('processing'))).toBe(true)
    expect(isActive(job('succeeded'))).toBe(false)
    expect(isActive(job('failed'))).toBe(false)
  })

  it('polls only while at least one job is active', () => {
    expect(anyActive([job('succeeded'), job('failed')])).toBe(false)
    expect(anyActive([job('succeeded'), job('processing')])).toBe(true)
    expect(anyActive([])).toBe(false)
  })

  it('labels statuses and worker stages in plain words', () => {
    expect(statusLabel('succeeded')).toBe('Completed')
    expect(statusLabel('processing')).toBe('Processing')
    expect(stageLabel('fetching')).toBe('Downloading video')
    expect(stageLabel('analysing')).toBe('Tracking players')
    expect(stageLabel(null)).toBe('')
    expect(stageLabel('something-new')).toBe('something-new')
  })
})
