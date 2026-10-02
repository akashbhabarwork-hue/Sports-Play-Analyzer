import { useState } from 'react'
import { sortPlayers, teamName } from '../logic/insights'
import type { SortDir, SortKey } from '../logic/insights'
import type { PlayerStats } from '../types'

const COLUMNS: { key: SortKey; label: string; numeric: boolean }[] = [
  { key: 'player_id', label: 'Player', numeric: false },
  { key: 'team', label: 'Team', numeric: false },
  { key: 'distance_rel', label: 'Distance (rel)', numeric: true },
  { key: 'distance_px', label: 'Distance (px)', numeric: true },
  { key: 'frames_visible', label: 'Frames visible', numeric: true },
  { key: 'possession_pct', label: 'Possession %', numeric: true },
]

export function TeamDot({ team }: { team: string | null }) {
  const cls = team === 'A' ? 'team-a' : team === 'B' ? 'team-b' : 'team-none'
  return <span className={`team-dot ${cls}`} aria-hidden="true" />
}

/** Sortable per-player stats; activating a row opens that player's heatmap. */
export function PlayerStatsTable({ players, onOpen }: { players: PlayerStats[]; onOpen: (id: number) => void }) {
  const [key, setKey] = useState<SortKey>('distance_rel')
  const [dir, setDir] = useState<SortDir>('desc')

  function sortBy(next: SortKey) {
    if (next === key) setDir(dir === 'asc' ? 'desc' : 'asc')
    else {
      setKey(next)
      setDir(next === 'player_id' || next === 'team' ? 'asc' : 'desc')
    }
  }

  if (players.length === 0) return <p className="muted">No players were tracked in this clip.</p>

  return (
    <div className="table-scroll">
      <table className="stats-table">
        <caption className="sr-only">Per-player stats. Select a row to open that player's heatmap.</caption>
        <thead>
          <tr>
            {COLUMNS.map((c) => (
              <th key={c.key} scope="col" aria-sort={key === c.key ? (dir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  className={c.numeric ? 'num right' : undefined}>
                <button type="button" className="sort-btn" onClick={() => sortBy(c.key)}>
                  {c.label}
                  <span aria-hidden="true">{key === c.key ? (dir === 'asc' ? ' ▲' : ' ▼') : ''}</span>
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortPlayers(players, key, dir).map((p) => (
            <tr key={p.player_id} className="clickable" tabIndex={0} onClick={() => onOpen(p.player_id)}
                onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onOpen(p.player_id))}
                aria-label={`Player ${p.player_id}, open heatmap`}>
              <td>
                <TeamDot team={p.team} /> <strong>#{p.player_id}</strong>
              </td>
              <td>{teamName(p.team)}</td>
              <td className="num right">{p.distance_rel.toFixed(2)}</td>
              <td className="num right">{Math.round(p.distance_px).toLocaleString()}</td>
              <td className="num right">{p.frames_visible}</td>
              <td className="num right">{p.possession_pct.toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
