import { summarize } from '../logic/results'
import type { Stats } from '../types'

export function StatsCards({ stats }: { stats: Stats }) {
  const s = summarize(stats)
  return (
    <dl className="stats-cards">
      <div className="card stat">
        <dt>Players tracked</dt>
        <dd>{s.playersTracked}</dd>
      </div>
      <div className="card stat">
        <dt>Ball visible</dt>
        <dd>{s.ballVisiblePct}%</dd>
      </div>
      <div className="card stat">
        <dt>Most possession</dt>
        <dd>{s.topPossession ? `#${s.topPossession.playerId} · ${s.topPossession.pct}%` : '—'}</dd>
      </div>
      <div className="card stat">
        <dt title="Sum of every player's distance, in frame diagonals (the camera moves, so pixels aren't metres)">
          Total distance
        </dt>
        <dd>{s.totalDistanceRel} × frame</dd>
      </div>
    </dl>
  )
}
