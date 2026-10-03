import { useId, useRef, useState } from 'react'
import type { DragEvent, FormEvent, KeyboardEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ApiError, api } from '../api'
import { sportArt } from '../assets/brand'
import { CloseIcon, InfoIcon, LinkIcon, UploadIcon, VideoIcon } from '../components/icons'
import { formatBytes, formatDuration } from '../logic/format'
import { checkDuration, checkFile, checkUrl } from '../logic/precheck'
import { readClipMeta } from '../media'
import type { ClipMeta } from '../media'
import type { Sport } from '../types'
import './new-analysis.css'

type Tab = 'upload' | 'url'
const TABS: { id: Tab; label: string; icon: typeof UploadIcon }[] = [
  { id: 'upload', label: 'Upload video', icon: UploadIcon },
  { id: 'url', label: 'YouTube link', icon: LinkIcon },
]
const SPORTS: { id: Sport; label: string }[] = [
  { id: 'football', label: 'Football' },
  { id: 'basketball', label: 'Basketball' },
]
const ACCEPT = 'video/mp4,video/quicktime,video/webm,video/x-matroska,video/x-msvideo,.mp4,.mov,.webm,.mkv,.avi'

function messageOf(err: unknown): string {
  return err instanceof ApiError ? err.message : 'Could not reach the server. Please try again.'
}

export function NewAnalysisPage() {
  const [params, setParams] = useSearchParams()
  const tab: Tab = params.get('tab') === 'url' ? 'url' : 'upload'
  const navigate = useNavigate()
  const ids = { title: useId(), url: useId(), sport: useId() }
  const inputRef = useRef<HTMLInputElement>(null)

  const [file, setFile] = useState<File | null>(null)
  const [meta, setMeta] = useState<ClipMeta | null>(null)
  const [dragging, setDragging] = useState(false)
  const [url, setUrl] = useState('')
  const [sport, setSport] = useState<Sport>('football')
  const [title, setTitle] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function switchTab(next: Tab) {
    setError(null)
    setParams(next === 'url' ? { tab: 'url' } : {}, { replace: true })
  }

  function onTabKey(e: KeyboardEvent<HTMLButtonElement>) {
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      e.preventDefault()
      switchTab(tab === 'upload' ? 'url' : 'upload')
    }
  }

  async function pick(picked: File | null) {
    setError(null)
    setMeta(null)
    setFile(picked)
    if (!picked) return
    const basic = checkFile(picked)
    if (basic) {
      setError(basic)
      return
    }
    const m = await readClipMeta(picked)
    setMeta(m)
    setError(checkDuration(m.duration))
  }

  function clearFile() {
    setFile(null)
    setMeta(null)
    setError(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  function onDrop(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault()
    setDragging(false)
    void pick(e.dataTransfer.files?.[0] ?? null)
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    const problem =
      tab === 'upload'
        ? file
          ? checkFile(file) ?? (meta ? checkDuration(meta.duration) : null)
          : 'Choose a video file first.'
        : checkUrl(url)
    if (problem) {
      setError(problem)
      return
    }
    setBusy(true)
    setError(null)
    try {
      const details = { sport, title: title.trim() || undefined }
      const accepted =
        tab === 'upload' ? await api.uploadFile(file!, details) : await api.submitUrl(url.trim(), details)
      navigate(`/app/jobs/${accepted.job_id}`)
    } catch (err) {
      setError(messageOf(err)) // the server's words, e.g. CORRUPT_FILE (A2) or a 429
      setBusy(false)
    }
  }

  return (
    <section>
      <header className="page-header">
        <div>
          <h1>New analysis</h1>
          <p className="muted">Upload a short clip or paste a YouTube link. We'll track players and build the stats.</p>
        </div>
      </header>

      <div className="new-grid">
        <form className="card new-form" onSubmit={submit} noValidate>
          <div className="segmented" role="tablist" aria-label="Video source">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                role="tab"
                id={`tab-${id}`}
                aria-selected={tab === id}
                aria-controls={`panel-${id}`}
                tabIndex={tab === id ? 0 : -1}
                className={tab === id ? 'seg active' : 'seg'}
                onClick={() => switchTab(id)}
                onKeyDown={onTabKey}
              >
                <Icon size={18} /> {label}
              </button>
            ))}
          </div>

          {tab === 'upload' ? (
            <div role="tabpanel" id="panel-upload" aria-labelledby="tab-upload" className="panel">
              {!file ? (
                <label
                  className={dragging ? 'dropzone dragging' : 'dropzone'}
                  onDragOver={(e) => {
                    e.preventDefault()
                    setDragging(true)
                  }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={onDrop}
                >
                  <input
                    ref={inputRef}
                    type="file"
                    accept={ACCEPT}
                    className="sr-only"
                    disabled={busy}
                    onChange={(e) => void pick(e.target.files?.[0] ?? null)}
                  />
                  <span className="dropzone-icon">
                    <UploadIcon size={26} />
                  </span>
                  <strong>Drag and drop a video, or click to browse</strong>
                  <span className="muted small">MP4, MOV, WebM, MKV, AVI · max 60 s · max 100 MB</span>
                </label>
              ) : (
                <div className="file-row">
                  {meta?.thumbnail ? (
                    <img className="file-thumb" src={meta.thumbnail} alt="" />
                  ) : (
                    <span className="file-thumb placeholder">
                      <VideoIcon />
                    </span>
                  )}
                  <div className="file-info">
                    <strong className="ellipsis">{file.name}</strong>
                    <span className="muted small num">
                      {formatBytes(file.size)} · {meta ? formatDuration(meta.duration) : 'reading…'}
                    </span>
                  </div>
                  <button type="button" className="icon-btn" aria-label="Remove file" onClick={clearFile} disabled={busy}>
                    <CloseIcon />
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div role="tabpanel" id="panel-url" aria-labelledby="tab-url" className="panel field">
              <label className="field-label" htmlFor={ids.url}>
                YouTube link
              </label>
              <input
                id={ids.url}
                className="input"
                type="url"
                inputMode="url"
                placeholder="https://www.youtube.com/watch?v=…"
                value={url}
                disabled={busy}
                onChange={(e) => setUrl(e.target.value)}
              />
              <span className="field-help">Public videos up to 60 seconds.</span>
            </div>
          )}

          <fieldset className="field sport-field">
            <legend className="field-label">Sport</legend>
            <div className="sport-options">
              {SPORTS.map(({ id, label }) => (
                <label key={id} className={sport === id ? 'sport-option active' : 'sport-option'}>
                  <img className="sport-field-art" src={sportArt[id].field} alt="" />
                  <span className="sport-option-row">
                    <input type="radio" name="sport" value={id} checked={sport === id} onChange={() => setSport(id)} disabled={busy} />
                    <img className="sport-ball" src={sportArt[id].ball} alt="" width={22} height={22} />
                    {label}
                  </span>
                </label>
              ))}
            </div>
            <span className="field-help">Used for the pitch or court outline on heatmaps.</span>
          </fieldset>

          <div className="field">
            <label className="field-label" htmlFor={ids.title}>
              Title <span className="muted">(optional)</span>
            </label>
            <input
              id={ids.title}
              className="input"
              maxLength={120}
              placeholder="e.g. Semi-final, second half"
              value={title}
              disabled={busy}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          {error && (
            <p className="alert" role="alert">
              {error}
            </p>
          )}

          <button type="submit" className="btn btn-primary btn-block btn-tall" disabled={busy}>
            {busy ? (
              <>
                <span className="spinner" aria-hidden="true" /> {tab === 'upload' ? 'Uploading…' : 'Submitting…'}
              </>
            ) : (
              'Start analysis →'
            )}
          </button>
        </form>

        <aside className="card tips" aria-label="Tips for best results">
          <h2>
            <InfoIcon /> Tips for best results
          </h2>
          <ul>
            <li>Use clear footage: sharp, well-lit, not too zoomed in.</li>
            <li>Keep clips to 60 seconds or less.</li>
            <li>Show the whole pitch or court where possible; wide shots track best.</li>
            <li>Game footage or drills both work.</li>
          </ul>
        </aside>
      </div>
    </section>
  )
}
