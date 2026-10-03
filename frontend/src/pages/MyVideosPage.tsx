import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api'
import { artFor, brand } from '../assets/brand'
import { CopyIcon, PlusIcon, VideoIcon } from '../components/icons'
import { RowMenu } from '../components/RowMenu'
import { StatusChip } from '../components/StatusChip'
import { usePolling } from '../hooks/usePolling'
import { formatDateTime, formatDuration } from '../logic/format'
import { POLL_MS, anyActive, stageLabel } from '../logic/jobs'
import { FILTERS, countByFilter, filterJobs, jobTitle, resubmitAction, sportLabel } from '../logic/videos'
import type { Filter } from '../logic/videos'
import type { JobSummary } from '../types'
import './videos.css'

function EmptyArt() {
  return <img className="empty-art" src={brand.tactics} alt="" width={120} height={120} />
}

export function MyVideosPage() {
  const navigate = useNavigate()
  const [jobs, setJobs] = useState<JobSummary[] | null>(null)
  const [filter, setFilter] = useState<Filter>('all')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setJobs(await api.listJobs())
      setError(null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load your videos.')
      throw err // the poller just tries again on its next tick
    }
  }, [])

  useEffect(() => {
    load().catch(() => undefined)
  }, [load])

  // Poll every 2 s only while something is queued/processing; paused while the tab is hidden.
  usePolling(load, POLL_MS, jobs !== null && anyActive(jobs))

  async function resubmit(job: JobSummary) {
    const action = resubmitAction(job)
    if (action.kind === 'upload') {
      navigate(action.to)
      return
    }
    try {
      const accepted = await api.submitUrl(action.url, action.details)
      navigate(`/app/jobs/${accepted.job_id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not resubmit this video.')
    }
  }

  async function copyId(id: string) {
    try {
      await navigator.clipboard.writeText(id)
      setNotice('Job ID copied')
    } catch {
      setNotice(`Job ID: ${id}`)
    }
  }

  const counts = jobs ? countByFilter(jobs) : null
  const shown = jobs ? filterJobs(jobs, filter) : []

  return (
    <section>
      <header className="page-header">
        <div>
          <h1>My videos</h1>
          <p className="muted">Your analyses, newest first.</p>
        </div>
        <Link className="btn btn-primary" to="/app/new">
          <PlusIcon size={18} /> New analysis
        </Link>
      </header>

      {counts && counts.all > 0 && (
        <div className="filters" role="group" aria-label="Filter by status">
          {FILTERS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              className={filter === id ? 'filter active' : 'filter'}
              aria-pressed={filter === id}
              onClick={() => setFilter(id)}
            >
              {label} <span className="filter-count num">{counts[id]}</span>
            </button>
          ))}
        </div>
      )}

      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      <p className="sr-only" role="status" aria-live="polite">
        {notice}
      </p>

      {jobs === null && !error && <p className="muted">Loading…</p>}

      {jobs?.length === 0 && (
        <div className="card empty">
          <EmptyArt />
          <h2>No videos yet</h2>
          <p className="muted">Upload a clip or paste a YouTube link to get your first analysis.</p>
          <Link className="btn btn-primary" to="/app/new">
            Start your first analysis
          </Link>
        </div>
      )}

      {jobs && jobs.length > 0 && shown.length === 0 && (
        <p className="card center muted">No videos in “{FILTERS.find((f) => f.id === filter)?.label}”.</p>
      )}

      {shown.length > 0 && (
        <div className="card table-card">
          <table className="videos">
            <thead>
              <tr>
                <th scope="col">Video</th>
                <th scope="col">Sport</th>
                <th scope="col">Status</th>
                <th scope="col">Created</th>
                <th scope="col">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {shown.map((job) => {
                const title = jobTitle(job)
                return (
                  <tr key={job.id}>
                    <td data-label="Video">
                      <Link to={`/app/jobs/${job.id}`} className="video-cell">
                        {job.thumbnail_url ? (
                          <img className="thumb" src={job.thumbnail_url} alt="" loading="lazy" />
                        ) : (
                          <span className="thumb placeholder">
                            <VideoIcon size={18} />
                          </span>
                        )}
                        <span className="video-text">
                          <strong className="ellipsis">{title}</strong>
                          <span className="muted small num">{formatDuration(job.duration_s)}</span>
                        </span>
                      </Link>
                    </td>
                    <td data-label="Sport">
                      <span className="sport-cell">
                        <img src={artFor(job.sport).ball} alt="" width={20} height={20} />
                        {sportLabel(job.sport)}
                      </span>
                    </td>
                    <td data-label="Status">
                      <div className="status-cell">
                        <StatusChip status={job.status} />
                        {job.status === 'processing' && (
                          <span className="inline-progress">
                            <span className="bar" role="progressbar" aria-valuemin={0} aria-valuemax={100}
                                  aria-valuenow={job.progress} aria-label={`${title}: ${stageLabel(job.stage)}`}>
                              <span style={{ width: `${job.progress}%` }} />
                            </span>
                            <span className="muted small num">{job.progress}%</span>
                          </span>
                        )}
                        {job.status === 'failed' && job.error && (
                          <span className="muted small row-error">{job.error.message ?? job.error.code}</span>
                        )}
                      </div>
                    </td>
                    <td data-label="Created" className="num">
                      {formatDateTime(job.created_at)}
                    </td>
                    <td className="actions">
                      {job.status === 'succeeded' && (
                        <Link className="btn btn-secondary btn-sm" to={`/app/jobs/${job.id}`}>
                          View results
                        </Link>
                      )}
                      {job.status === 'failed' && (
                        <button type="button" className="btn btn-secondary btn-sm" onClick={() => resubmit(job)}>
                          Resubmit
                        </button>
                      )}
                      {(job.status === 'queued' || job.status === 'processing') && (
                        <Link className="btn btn-ghost btn-sm" to={`/app/jobs/${job.id}`}>
                          View progress
                        </Link>
                      )}
                      <RowMenu
                        label={`More actions for ${title}`}
                        items={[
                          { label: 'Open', onSelect: () => navigate(`/app/jobs/${job.id}`) },
                          { label: 'Copy job ID', icon: <CopyIcon size={16} />, onSelect: () => copyId(job.id) },
                        ]}
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
