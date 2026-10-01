// Thin fetch wrapper that understands the backend error envelope:
// { "error": { "code": string, "message": string } }

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

async function toApiError(res: Response): Promise<ApiError> {
  let body: ErrorEnvelope = {}
  try {
    body = (await res.json()) as ErrorEnvelope
  } catch {
    // non-JSON error body; fall back to the status text
  }
  return new ApiError(
    res.status,
    body.error?.code ?? 'HTTP_ERROR',
    body.error?.message ?? (res.statusText || 'Request failed'),
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
