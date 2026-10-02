import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, api } from '../api'
import { ProgressBar } from '../components/ProgressBar'
import { StatusChip } from '../components/StatusChip'
import { usePolling } from '../hooks/usePolling'
import { POLL_MS, anyActive, formatWhen, shortId, stageLabel } from '../logic/jobs'
import type { JobSummary } from '../types'

export function JobsPage() {
  const [jobs, setJobs] = useState<JobSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setJobs(await api.listJobs())
      setError(null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load your jobs.')
      throw err // let the poller know; it simply tries again next tick
    }
  }, [])

  useEffect(() => {
    load().catch(() => undefined)
  }, [load])

  // Poll every 2 s only while something is queued/processing; stop when all are finished.
  usePolling(load, POLL_MS, jobs !== null && anyActive(jobs))

  return (
    <section>
      <div className="page-head">
        <h1>Your analyses</h1>
        <Link className="button" to="/app/submit">
          New analysis
        </Link>
      </div>
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      {jobs === null && !error && <p className="muted">Loading…</p>}
      {jobs?.length === 0 && (
        <div className="card center">
          <p>No analyses yet.</p>
          <Link to="/app/submit">Upload a clip or paste a YouTube link</Link>
        </div>
      )}
      {jobs && jobs.length > 0 && (
        <table className="jobs card">
          <thead>
            <tr>
              <th scope="col">Job</th>
              <th scope="col">Submitted</th>
              <th scope="col">Status</th>
              <th scope="col">Progress</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id}>
                <td>
                  <Link to={`/app/jobs/${job.id}`}>#{shortId(job.id)}</Link>
                </td>
                <td>{formatWhen(job.created_at)}</td>
                <td>
                  <StatusChip status={job.status} />
                </td>
                <td>
                  {job.status === 'failed' ? (
                    <span className="error-text">{job.error?.message ?? 'Failed'}</span>
                  ) : (
                    <ProgressBar value={job.progress} label={stageLabel(job.stage)} />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
