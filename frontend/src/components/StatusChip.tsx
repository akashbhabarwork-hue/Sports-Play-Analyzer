import { statusLabel } from '../logic/jobs'
import type { JobStatus } from '../types'
import { AlertIcon, CheckIcon, ClockIcon } from './icons'
import './status.css'

const ICON = { queued: ClockIcon, processing: null, succeeded: CheckIcon, failed: AlertIcon } as const

/** Status pill: grey queued, indigo processing (with live dot), green completed, red failed. */
export function StatusChip({ status }: { status: JobStatus }) {
  const Icon = ICON[status]
  return (
    <span className={`status status-${status}`}>
      {Icon ? <Icon size={14} /> : <span className="status-dot" aria-hidden="true" />}
      {statusLabel(status)}
    </span>
  )
}
