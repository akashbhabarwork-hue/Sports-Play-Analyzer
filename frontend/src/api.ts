// Thin fetch wrapper that understands the backend error envelope:
// { "error": { "code": string, "message": string } }
import type {
  Heatmap,
  JobAccepted,
  JobDetail,
  JobSummary,
  Me,
  PlayerDetail,
  Sport,
  Stats,
} from './types'

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

type ErrorEnvelope = { error?: { code?: string; message?: string } }

const FRIENDLY: Record<number, string> = {
  413: 'That file is larger than 100 MB.',
  429: 'Too many submissions — please try again in a minute.',
}

export async function toApiError(res: Response): Promise<ApiError> {
  let body: ErrorEnvelope = {}
  try {
    body = (await res.json()) as ErrorEnvelope
  } catch {
    // non-JSON error body; fall back to the status text
  }
  return new ApiError(
    res.status,
    body.error?.code ?? `HTTP_${res.status}`,
    body.error?.message ?? FRIENDLY[res.status] ?? 'Something went wrong. Please try again.',
  )
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    credentials: 'same-origin',
    ...init,
    // X-Requested-With is required by the server's CSRF check on unsafe methods.
    headers: { Accept: 'application/json', 'X-Requested-With': 'fetch', ...init.headers },
  })
  if (!res.ok) {
    throw await toApiError(res)
  }
  if (res.status === 204) {
    return undefined as T
  }
  return (await res.json()) as T
}

const job = (id: string) => `/api/jobs/${encodeURIComponent(id)}`

export interface SubmitDetails {
  sport: Sport
  title?: string
}

export const api = {
  me: () => apiFetch<Me>('/api/me'),
  logout: () => apiFetch<void>('/auth/logout', { method: 'POST' }),
  listJobs: () => apiFetch<{ jobs: JobSummary[] }>('/api/jobs').then((r) => r.jobs),
  getJob: (id: string) => apiFetch<JobDetail>(job(id)),
  getStats: (id: string) => apiFetch<Stats>(`${job(id)}/stats`),
  getPlayer: (id: string, playerId: number) =>
    apiFetch<PlayerDetail>(`${job(id)}/players/${playerId}`),
  getHeatmap: (id: string, team: 'all' | 'A' | 'B') =>
    apiFetch<Heatmap>(`${job(id)}/heatmap?team=${team}`),
  videoUrl: (id: string) => `${job(id)}/video`,
  submitUrl: (url: string, details: SubmitDetails) =>
    apiFetch<JobAccepted>('/api/jobs/url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, sport: details.sport, title: details.title || null }),
    }),
  // FormData sets its own multipart Content-Type (with boundary): never set it by hand.
  uploadFile: (file: File, details: SubmitDetails) => {
    const form = new FormData()
    form.append('file', file)
    form.append('sport', details.sport)
    if (details.title) form.append('title', details.title)
    return apiFetch<JobAccepted>('/api/jobs/upload', { method: 'POST', body: form })
  },
}
