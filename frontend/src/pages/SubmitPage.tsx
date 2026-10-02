import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ApiError, api } from '../api'
import { checkDuration, checkFile, checkUrl } from '../logic/precheck'

type Tab = 'upload' | 'url'

/** Reads the duration from the file's metadata in a detached <video> (nothing is uploaded). */
function readDuration(file: File): Promise<number> {
  return new Promise((resolve) => {
    const video = document.createElement('video')
    const url = URL.createObjectURL(file)
    const done = (seconds: number) => {
      URL.revokeObjectURL(url)
      resolve(seconds)
    }
    video.preload = 'metadata'
    video.onloadedmetadata = () => done(video.duration)
    video.onerror = () => done(Number.NaN) // codec the browser can't read: server decides
    video.src = url
  })
}

function messageOf(err: unknown): string {
  return err instanceof ApiError ? err.message : 'Could not reach the server. Please try again.'
}

export function SubmitPage() {
  const [params, setParams] = useSearchParams()
  const tab: Tab = params.get('tab') === 'url' ? 'url' : 'upload'
  const navigate = useNavigate()
  const [file, setFile] = useState<File | null>(null)
  const [url, setUrl] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function switchTab(next: Tab) {
    setError(null)
    setParams(next === 'url' ? { tab: 'url' } : {}, { replace: true })
  }

  async function onPickFile(picked: File | null) {
    setFile(picked)
    setError(null)
    if (!picked) return
    const problem = checkFile(picked) ?? checkDuration(await readDuration(picked))
    setError(problem)
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    const problem = tab === 'upload' ? (file ? checkFile(file) : 'Choose a video file.') : checkUrl(url)
    if (problem) {
      setError(problem)
      return
    }
    setBusy(true)
    setError(null)
    try {
      const accepted = tab === 'upload' ? await api.uploadFile(file!) : await api.submitUrl(url.trim())
      navigate(`/app/jobs/${accepted.job_id}`)
    } catch (err) {
      setError(messageOf(err)) // the server's own words, e.g. CORRUPT_FILE (scenario A2)
      setBusy(false)
    }
  }

  return (
    <section className="card submit">
      <h1>New analysis</h1>
      <div className="tabs" role="tablist" aria-label="Video source">
        <button type="button" role="tab" aria-selected={tab === 'upload'}
                className={tab === 'upload' ? 'tab active' : 'tab'} onClick={() => switchTab('upload')}>
          Upload a file
        </button>
        <button type="button" role="tab" aria-selected={tab === 'url'}
                className={tab === 'url' ? 'tab active' : 'tab'} onClick={() => switchTab('url')}>
          YouTube link
        </button>
      </div>

      <form onSubmit={submit} className="stack" noValidate>
        {tab === 'upload' ? (
          <label className="field">
            <span>Video file (MP4, MOV, WebM, MKV or AVI · up to 100 MB · up to 60 s)</span>
            <input type="file" accept="video/*,.mkv,.avi" disabled={busy}
                   onChange={(e) => onPickFile(e.target.files?.[0] ?? null)} />
          </label>
        ) : (
          <label className="field">
            <span>YouTube link (up to 60 s)</span>
            <input type="url" inputMode="url" placeholder="https://www.youtube.com/watch?v=…"
                   value={url} disabled={busy} onChange={(e) => setUrl(e.target.value)} />
          </label>
        )}

        {error && (
          <p className="alert" role="alert">
            {error}
          </p>
        )}

        <div>
          <button type="submit" disabled={busy}>
            {busy ? (tab === 'upload' ? 'Uploading…' : 'Submitting…') : 'Analyse'}
          </button>
        </div>
      </form>
    </section>
  )
}
