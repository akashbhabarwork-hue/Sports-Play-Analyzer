// Browser-only helpers (need <video>/<canvas>; checked by hand in the walkthrough, not Vitest).

export interface ClipMeta {
  duration: number // NaN if the browser can't read it (e.g. some .mkv/.avi codecs)
  thumbnail: string | null // JPEG data URL of an early frame, or null
}

const TIMEOUT_MS = 5000
const THUMB_WIDTH = 240

/** Reads duration and grabs an early frame from a local file; nothing is uploaded. */
export function readClipMeta(file: File): Promise<ClipMeta> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file)
    const video = document.createElement('video')
    let done = false
    const finish = (meta: ClipMeta) => {
      if (done) return
      done = true
      clearTimeout(timer)
      URL.revokeObjectURL(url)
      video.removeAttribute('src')
      resolve(meta)
    }
    const timer = setTimeout(() => finish({ duration: video.duration, thumbnail: null }), TIMEOUT_MS)

    video.preload = 'metadata'
    video.muted = true
    video.playsInline = true
    video.onerror = () => finish({ duration: Number.NaN, thumbnail: null })
    video.onloadedmetadata = () => {
      // Seek a little in: frame 0 is often black.
      video.currentTime = Math.min(0.5, (video.duration || 1) / 2)
    }
    video.onseeked = () => {
      let thumbnail: string | null = null
      try {
        const h = Math.round((THUMB_WIDTH * video.videoHeight) / (video.videoWidth || 1))
        const canvas = document.createElement('canvas')
        canvas.width = THUMB_WIDTH
        canvas.height = h || 135
        canvas.getContext('2d')?.drawImage(video, 0, 0, canvas.width, canvas.height)
        thumbnail = canvas.toDataURL('image/jpeg', 0.7)
      } catch {
        thumbnail = null
      }
      finish({ duration: video.duration, thumbnail })
    }
    video.src = url
  })
}
