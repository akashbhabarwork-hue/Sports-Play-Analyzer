import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, apiFetch } from './api'

function respond(status: number, body?: unknown) {
  const init = { status, headers: { 'Content-Type': 'application/json' } }
  const res = body === undefined ? new Response(null, init) : new Response(JSON.stringify(body), init)
  const fetchMock = vi.fn().mockResolvedValue(res)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

async function failure(p: Promise<unknown>): Promise<ApiError> {
  try {
    await p
  } catch (e) {
    return e as ApiError
  }
  throw new Error('expected the request to fail')
}

afterEach(() => vi.unstubAllGlobals())

describe('apiFetch', () => {
  it('sends the CSRF header and same-origin cookies', async () => {
    const fetchMock = respond(200, { ok: true })
    await apiFetch('/api/me')
    const [, init] = fetchMock.mock.calls[0]
    expect(init.credentials).toBe('same-origin')
    expect(init.headers['X-Requested-With']).toBe('fetch')
  })

  it('turns the error envelope into an ApiError with the server message', async () => {
    respond(422, { error: { code: 'CORRUPT_FILE', message: "We couldn't read this video." } })
    const err = await failure(apiFetch('/api/jobs/upload'))
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(422)
    expect(err.code).toBe('CORRUPT_FILE')
    expect(err.message).toBe("We couldn't read this video.")
  })

  it('gives a readable message when the body is not our envelope', async () => {
    respond(429, 'rate limited')
    const err = await failure(apiFetch('/api/jobs/url'))
    expect(err.code).toBe('HTTP_429')
    expect(err.message).toMatch(/try again in a minute/)
  })

  it('returns undefined for 204', async () => {
    respond(204)
    await expect(apiFetch('/auth/logout', { method: 'POST' })).resolves.toBeUndefined()
  })
})

describe('api', () => {
  it('logs out with POST so a cross-site link cannot log users out', async () => {
    const fetchMock = respond(204)
    await api.logout()
    expect(fetchMock.mock.calls[0][0]).toBe('/auth/logout')
    expect(fetchMock.mock.calls[0][1].method).toBe('POST')
  })

  it('escapes job ids in URLs', () => {
    expect(api.videoUrl('a/../b')).toBe('/api/jobs/a%2F..%2Fb/video')
  })

  it('unwraps the job list', async () => {
    respond(200, { jobs: [{ id: '1' }] })
    await expect(api.listJobs()).resolves.toEqual([{ id: '1' }])
  })
})
