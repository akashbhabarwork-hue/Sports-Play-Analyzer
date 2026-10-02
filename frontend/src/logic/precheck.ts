// Client-side pre-checks: UX only, so people don't wait for a 100 MB upload to be rejected.
// The server re-checks everything by content (magic bytes + ffprobe) and is the authority.

export const MAX_BYTES = 100 * 1024 * 1024
export const MAX_SECONDS = 60
const DURATION_TOLERANCE_S = 0.5 // containers often report a few frames over (server agrees)

export interface FileLike {
  name: string
  size: number
  type: string
}

export function checkFile(f: FileLike): string | null {
  if (f.size === 0) return 'That file is empty.'
  if (f.size > MAX_BYTES) return 'That file is larger than 100 MB. Trim or compress it first.'
  // An empty type is common for .mkv/.avi; only reject what is clearly something else.
  if (f.type && !f.type.startsWith('video/')) return 'That file is not a video.'
  return null
}

export function checkDuration(seconds: number): string | null {
  if (!Number.isFinite(seconds)) return null // browser couldn't tell; let the server decide
  if (seconds > MAX_SECONDS + DURATION_TOLERANCE_S) {
    return `This video is ${Math.round(seconds)} s long; the limit is ${MAX_SECONDS} s. Trim it first.`
  }
  return null
}

export function checkUrl(value: string): string | null {
  const text = value.trim()
  if (!text) return 'Paste a YouTube link.'
  try {
    new URL(text)
  } catch {
    return 'Paste the full link, starting with https://'
  }
  return null
}
