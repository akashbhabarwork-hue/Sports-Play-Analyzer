import { useState } from 'react'
import { Link } from 'react-router-dom'
import { formatBytes, formatDuration } from '../logic/format'
import { stageLabel } from '../logic/jobs'
import { errorHelp } from '../logic/results'
import { stepStates, steps } from '../logic/stepper'
import { jobTitle } from '../logic/videos'
import type { JobDetail } from '../types'
import { AlertIcon, BackIcon, CheckIcon, CopyIcon, VideoIcon } from './icons'
import { StatusChip } from './StatusChip'
import './processing.css'

/** Original abstract figure (no likeness): a runner made of simple strokes + motion arcs. */
function PlayerArt() {
  return (
    <svg className="processing-art" viewBox="0 0 160 140" aria-hidden="true">
      <circle cx="80" cy="70" r="62" fill="var(--primary-soft)" />
      <path d="M40 112c22-8 58-8 80 0" stroke="var(--border)" strokeWidth="3" fill="none" strokeLinecap="round" />
      <g stroke="var(--primary)" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" fill="none">
        <circle cx="92" cy="34" r="9" fill="var(--primary)" stroke="none" />
        <path d="M88 46 78 74l16 14 6 22" />
        <path d="M78 74 62 92 48 92" />
        <path d="M86 54l18 10 12-8" />
        <path d="M84 52 66 58 58 70" />
      </g>
      <g stroke="var(--team-b)" strokeWidth="3" strokeLinecap="round" opacity="0.6">
        <path d="M30 48h18M24 62h20M32 76h14" />
      </g>
      <circle cx="116" cy="104" r="7" fill="var(--ball)" />
    </svg>
  )
}

export function ProcessingView({ job }: { job: JobDetail }) {
  const [copied, setCopied] = useState(false)
  const failed = job.status === 'failed'
  const states = stepStates(job)
  const current = steps(job.source_type).find((s) => states[s.id] === 'current')
  const help = failed && job.error ? errorHelp(job.error.code) : null

  async function copyId() {
    try {
      await navigator.clipboard.writeText(job.id)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard blocked: the id is visible on screen anyway */
    }
  }

  return (
    <section className="processing">
      <Link to="/app" className="back-link">
        <BackIcon size={18} /> Back to dashboard
      </Link>

      <header className="page-header">
        <div>
          <h1>{failed ? 'Analysis failed' : 'Processing video'}</h1>
          <p className="muted">{failed ? 'Nothing was saved for this video.' : 'This usually takes 1–3 minutes. This page updates by itself.'}</p>
        </div>
        <div className="id-chip">
          <span className="muted small">Job ID</span>
          <code>{job.id.slice(0, 8)}…</code>
          <button type="button" className="icon-btn" onClick={copyId} aria-label="Copy job ID">
            {copied ? <CheckIcon size={16} /> : <CopyIcon size={16} />}
          </button>
          <span className="sr-only" role="status">
            {copied ? 'Job ID copied' : ''}
          </span>
        </div>
      </header>

      <div className="processing-grid">
        <div className="processing-main">
          <div className="card source-card">
            {job.thumbnail_url ? (
              <img className="source-thumb" src={job.thumbnail_url} alt="" />
            ) : (
              <span className="source-thumb placeholder">
                <VideoIcon />
              </span>
            )}
            <div className="source-info">
              <strong className="ellipsis">{jobTitle(job)}</strong>
              {job.source_url && <span className="muted small ellipsis">{job.source_url}</span>}
              <span className="muted small num">
                {formatDuration(job.duration_s)} · {formatBytes(job.size_bytes)}
              </span>
            </div>
            <StatusChip status={job.status} />
          </div>

          {failed && job.error ? (
            <div className="card error-card" role="alert">
              <AlertIcon size={28} />
              <h2>{job.error.message ?? help?.title}</h2>
              {help && job.error.message && <p className="muted">{help.title}</p>}
              <code className="error-code">{job.error.code}</code>
              <div className="error-actions">
                {help?.action && (
                  <Link className="btn btn-primary" to={help.action.to}>
                    {help.action.label}
                  </Link>
                )}
                <Link className="btn btn-secondary" to="/app">
                  Back to dashboard
                </Link>
              </div>
            </div>
          ) : (
            <div className="card current-card">
              <div className="current-head">
                <span className="muted small">Current step</span>
                <strong>{current?.label ?? stageLabel(job.stage)}</strong>
              </div>
              <div className="bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={job.progress} aria-label="Overall progress">
                <span style={{ width: `${job.progress}%` }} />
              </div>
              <span className="muted small num">{job.progress}% complete</span>
            </div>
          )}

          <ol className="card stepper" aria-label="Processing steps">
            {steps(job.source_type).map(({ id, label }) => {
              const state = states[id]
              return (
                <li key={id} className={`step-item ${state}`} aria-current={state === 'current' ? 'step' : undefined}>
                  <span className="step-marker" aria-hidden="true">
                    {state === 'done' && <CheckIcon size={16} />}
                    {state === 'current' && <span className="step-spinner" />}
                    {state === 'failed' && <AlertIcon size={16} />}
                  </span>
                  <span className="step-label">{label}</span>
                  <span className="sr-only">
                    {{ done: 'done', current: 'in progress', todo: 'not started', failed: 'failed' }[state]}
                  </span>
                </li>
              )
            })}
          </ol>
        </div>
        <PlayerArt />
      </div>
    </section>
  )
}
