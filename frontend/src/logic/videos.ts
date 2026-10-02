import type { SubmitDetails } from '../api'
import type { JobSummary, Sport } from '../types'

export type Filter = 'all' | 'processing' | 'completed' | 'failed'

export const FILTERS: { id: Filter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'processing', label: 'Processing' },
  { id: 'completed', label: 'Completed' },
  { id: 'failed', label: 'Failed' },
]

function bucket(job: Pick<JobSummary, 'status'>): Exclude<Filter, 'all'> {
  if (job.status === 'succeeded') return 'completed'
  if (job.status === 'failed') return 'failed'
  return 'processing' // queued or processing: both still running
}

export function countByFilter(jobs: Pick<JobSummary, 'status'>[]): Record<Filter, number> {
  const counts: Record<Filter, number> = { all: jobs.length, processing: 0, completed: 0, failed: 0 }
  for (const j of jobs) counts[bucket(j)] += 1
  return counts
}

export function filterJobs<T extends Pick<JobSummary, 'status'>>(jobs: T[], filter: Filter): T[] {
  return filter === 'all' ? jobs : jobs.filter((j) => bucket(j) === filter)
}

function shortUrl(url: string): string {
  try {
    const u = new URL(url)
    return `${u.hostname.replace(/^www\./, '')}${u.pathname}${u.search}`
  } catch {
    return url
  }
}

/** What to call a video in lists and headers: never invented, always from the job's fields. */
export function jobTitle(job: JobSummary): string {
  if (job.title) return job.title
  if (job.original_filename) return job.original_filename
  if (job.source_url) return shortUrl(job.source_url)
  return `Video #${job.id.slice(0, 8)}`
}

export function sportLabel(sport: Sport): string {
  return sport[0].toUpperCase() + sport.slice(1)
}

export type Resubmit =
  | { kind: 'url'; url: string; details: SubmitDetails }
  | { kind: 'upload'; to: string }

export function resubmitAction(job: JobSummary): Resubmit {
  if (job.source_type === 'url' && job.source_url) {
    return { kind: 'url', url: job.source_url, details: { sport: job.sport, title: job.title ?? undefined } }
  }
  return { kind: 'upload', to: '/app/new' }
}
