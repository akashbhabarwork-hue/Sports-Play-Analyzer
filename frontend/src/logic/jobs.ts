import type { JobStatus, JobSummary } from '../types'

export const POLL_MS = 2000

export function isActive(job: Pick<JobSummary, 'status'>): boolean {
  return job.status === 'queued' || job.status === 'processing'
}

export function anyActive(jobs: Pick<JobSummary, 'status'>[]): boolean {
  return jobs.some(isActive)
}

const STATUS: Record<JobStatus, string> = {
  queued: 'Queued',
  processing: 'Processing',
  succeeded: 'Completed',
  failed: 'Failed',
}

export function statusLabel(status: JobStatus): string {
  return STATUS[status] ?? status
}

// Worker stages from services/process.py (D-026).
const STAGES: Record<string, string> = {
  fetching: 'Downloading video',
  analysing: 'Tracking players',
  saving: 'Saving results',
}

export function stageLabel(stage: string | null): string {
  if (!stage) return ''
  return STAGES[stage] ?? stage
}

export function shortId(id: string): string {
  return id.slice(0, 8)
}

export function formatWhen(iso: string, now: Date = new Date()): string {
  const then = new Date(iso)
  const minutes = Math.round((now.getTime() - then.getTime()) / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  return then.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}
