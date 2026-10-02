import { describe, expect, it } from 'vitest'
import type { JobSummary } from '../types'
import { stepStates, steps } from './stepper'

const job = (over: Partial<JobSummary>) =>
  ({ status: 'processing', stage: null, source_type: 'upload', ...over }) as JobSummary

describe('steps', () => {
  it('shows "Fetching video" only for YouTube links', () => {
    expect(steps('upload').map((s) => s.id)).toEqual(['queued', 'analysing', 'computing', 'rendering', 'saving'])
    expect(steps('url').map((s) => s.id)).toEqual(['queued', 'fetching', 'analysing', 'computing', 'rendering', 'saving'])
  })

  it('uses the plain-language labels from the brief', () => {
    expect(steps('url').map((s) => s.label)).toEqual([
      'Queued',
      'Fetching video',
      'Analysing frames',
      'Computing stats & heatmaps',
      'Rendering annotated video',
      'Saving results',
    ])
  })
})

describe('stepStates', () => {
  it('queued job: only "Queued" is current', () => {
    expect(stepStates(job({ status: 'queued' }))).toEqual({
      queued: 'current', analysing: 'todo', computing: 'todo', rendering: 'todo', saving: 'todo',
    })
  })

  it('processing: earlier steps done, the backend stage current, later ones todo', () => {
    expect(stepStates(job({ stage: 'computing' }))).toEqual({
      queued: 'done', analysing: 'done', computing: 'current', rendering: 'todo', saving: 'todo',
    })
  })

  it('a just-claimed job without a stage yet shows the first worker step as current', () => {
    expect(stepStates(job({ source_type: 'url', stage: null })).fetching).toBe('current')
    expect(stepStates(job({ stage: null })).analysing).toBe('current')
  })

  it('succeeded: everything done', () => {
    expect(Object.values(stepStates(job({ status: 'succeeded' })))).toEqual(Array(5).fill('done'))
  })

  it('failed: marks the step that failed when the stage is known', () => {
    expect(stepStates(job({ status: 'failed', stage: 'rendering' }))).toEqual({
      queued: 'done', analysing: 'done', computing: 'done', rendering: 'failed', saving: 'todo',
    })
    expect(stepStates(job({ status: 'failed', stage: null })).queued).toBe('done')
  })
})
