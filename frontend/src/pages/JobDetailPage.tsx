import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ApiError, api } from '../api'
import { HeatmapPanel } from '../components/HeatmapPanel'
import { ProcessingView } from '../components/ProcessingView'
import { StatsCards } from '../components/StatsCards'
import { StatusChip } from '../components/StatusChip'
import { VideoPlayer } from '../components/VideoPlayer'
import { usePolling } from '../hooks/usePolling'
import { POLL_MS, formatWhen, isActive } from '../logic/jobs'
import { jobTitle } from '../logic/videos'
import type { JobDetail, Stats } from '../types'
import { NotFoundPage } from './NotFoundPage'

type Load =
  | { kind: 'loading' }
  | { kind: 'not-found' } // missing OR someone else's job: the API answers 404 for both (A3)
  | { kind: 'error'; message: string }
  | { kind: 'ready'; job: JobDetail }

export function JobDetailPage() {
  const { jobId = '' } = useParams()
  const [load, setLoad] = useState<Load>({ kind: 'loading' })
  const [stats, setStats] = useState<Stats | null>(null)

  const refresh = useCallback(async () => {
    try {
      setLoad({ kind: 'ready', job: await api.getJob(jobId) })
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setLoad({ kind: 'not-found' })
      } else {
        // A blip while polling keeps the job on screen; only a first load shows the error.
        const message = err instanceof ApiError ? err.message : 'Could not load this job.'
        setLoad((prev) => (prev.kind === 'ready' ? prev : { kind: 'error', message }))
      }
      throw err
    }
  }, [jobId])

  useEffect(() => {
    setLoad({ kind: 'loading' })
    setStats(null)
    refresh().catch(() => undefined)
  }, [refresh])

  const job = load.kind === 'ready' ? load.job : null
  usePolling(refresh, POLL_MS, job !== null && isActive(job))

  useEffect(() => {
    if (job?.status !== 'succeeded') return
    let cancelled = false
    api.getStats(job.id).then((s) => !cancelled && setStats(s)).catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [job?.id, job?.status])

  if (load.kind === 'loading') return <p className="muted">Loading…</p>
  if (load.kind === 'not-found') return <NotFoundPage what="Job" />
  if (load.kind === 'error') {
    return (
      <p className="alert" role="alert">
        {load.message}
      </p>
    )
  }

  const { job: j } = load
  // Queued, processing or failed → the processing view (stepper / error card). When polling
  // sees "succeeded" this same page switches to the results (T-096, T-097).
  if (j.status !== 'succeeded') return <ProcessingView job={j} />
  return (
    <section className="stack">
      <div className="page-head">
        <div>
          <h1 className="ellipsis">{jobTitle(j)}</h1>
          <p className="muted">Submitted {formatWhen(j.created_at)}</p>
        </div>
        <StatusChip status={j.status} />
      </div>
      <VideoPlayer src={api.videoUrl(j.id)} />
      {stats ? (
        <>
          <StatsCards stats={stats} />
          <HeatmapPanel jobId={j.id} stats={stats} />
        </>
      ) : (
        <p className="muted">Loading stats…</p>
      )}
    </section>
  )
}
