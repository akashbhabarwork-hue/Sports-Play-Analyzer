import type { JobSummary, Stage } from '../types'
import { STAGE_LABELS } from './jobs'

export type StepId = 'queued' | Stage
export type StepState = 'done' | 'current' | 'todo' | 'failed'

/** The processing stepper, in the worker's real order (backend core/pipeline.STAGES, D-031). */
export function steps(sourceType: JobSummary['source_type']): { id: StepId; label: string }[] {
  const ids: StepId[] =
    sourceType === 'url'
      ? ['queued', 'fetching', 'analysing', 'computing', 'rendering', 'saving']
      : ['queued', 'analysing', 'computing', 'rendering', 'saving']
  return ids.map((id) => ({ id, label: id === 'queued' ? 'Queued' : STAGE_LABELS[id] }))
}

export function stepStates(
  job: Pick<JobSummary, 'status' | 'stage' | 'source_type'>,
): Record<string, StepState> {
  const ids = steps(job.source_type).map((s) => s.id)
  const states: Record<string, StepState> = Object.fromEntries(ids.map((id) => [id, 'todo']))
  const mark = (upTo: number, at: StepState | null) =>
    ids.forEach((id, i) => {
      if (i < upTo) states[id] = 'done'
      else if (i === upTo && at) states[id] = at
    })

  if (job.status === 'succeeded') {
    ids.forEach((id) => (states[id] = 'done'))
  } else if (job.status === 'queued') {
    states.queued = 'current'
  } else {
    const at = job.stage ? ids.indexOf(job.stage) : -1
    if (job.status === 'processing') {
      mark(at >= 0 ? at : 1, 'current') // no stage yet: the first worker step is starting
    } else {
      mark(at >= 0 ? at : 1, at >= 0 ? 'failed' : null) // failed
    }
  }
  return states
}
