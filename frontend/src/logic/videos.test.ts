import { describe, expect, it } from 'vitest'
import type { JobSummary } from '../types'
import { countByFilter, filterJobs, jobTitle, resubmitAction, sportLabel } from './videos'

const base: JobSummary = {
  id: '3f2a9c10-aaaa-bbbb-cccc-000000000001',
  title: null,
  sport: 'football',
  source_type: 'upload',
  original_filename: 'derby.mp4',
  source_url: null,
  duration_s: 42,
  size_bytes: 1000,
  thumbnail_url: null,
  status: 'succeeded',
  progress: 100,
  stage: null,
  error: null,
  created_at: '2026-10-02T08:00:00Z',
  finished_at: null,
}
const job = (over: Partial<JobSummary>): JobSummary => ({ ...base, ...over })

describe('jobTitle', () => {
  it('prefers the title, then the file name, then the link, then a short id', () => {
    expect(jobTitle(job({ title: 'Semi final' }))).toBe('Semi final')
    expect(jobTitle(job({}))).toBe('derby.mp4')
    expect(jobTitle(job({ source_type: 'url', original_filename: null, source_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ' }))).toBe('youtube.com/watch?v=dQw4w9WgXcQ')
    expect(jobTitle(job({ original_filename: null }))).toBe('Video #3f2a9c10')
  })
})

describe('filters', () => {
  const jobs = [
    job({ status: 'queued' }),
    job({ status: 'processing' }),
    job({ status: 'succeeded' }),
    job({ status: 'succeeded' }),
    job({ status: 'failed' }),
  ]

  it('counts queued as processing (both are still running)', () => {
    expect(countByFilter(jobs)).toEqual({ all: 5, processing: 2, completed: 2, failed: 1 })
  })

  it('filters by the same buckets', () => {
    expect(filterJobs(jobs, 'processing').map((j) => j.status)).toEqual(['queued', 'processing'])
    expect(filterJobs(jobs, 'all')).toHaveLength(5)
  })
})

describe('resubmitAction', () => {
  it('re-posts the same link with its sport and title', () => {
    const j = job({ source_type: 'url', source_url: 'https://youtu.be/x', sport: 'basketball', title: 'Drill' })
    expect(resubmitAction(j)).toEqual({ kind: 'url', url: 'https://youtu.be/x', details: { sport: 'basketball', title: 'Drill' } })
  })

  it('sends uploads back to New analysis (the file is not kept in the browser)', () => {
    expect(resubmitAction(job({ status: 'failed' }))).toEqual({ kind: 'upload', to: '/app/new' })
  })
})

describe('sportLabel', () => {
  it('capitalises', () => {
    expect(sportLabel('basketball')).toBe('Basketball')
  })
})
