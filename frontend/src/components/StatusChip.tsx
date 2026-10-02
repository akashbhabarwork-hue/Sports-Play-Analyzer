import { statusLabel } from '../logic/jobs'
import type { JobStatus } from '../types'

export function StatusChip({ status }: { status: JobStatus }) {
  return <span className={`chip chip-${status}`}>{statusLabel(status)}</span>
}
