import { useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, api } from '../api'
import { parseSelection, selectorOptions } from '../logic/heatmap'
import type { Heatmap, PlayerDetail, Stats } from '../types'
import { HeatmapCanvas } from './HeatmapCanvas'
import { PlayerSelector } from './PlayerSelector'

/** Team heatmaps come with the stats (instant); a player's is fetched once, then cached. */
export function HeatmapPanel({ jobId, stats }: { jobId: string; stats: Stats }) {
  const options = useMemo(() => selectorOptions(stats), [stats])
  const [value, setValue] = useState('all')
  const [showTrack, setShowTrack] = useState(true)
  const [player, setPlayer] = useState<PlayerDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const cache = useRef(new Map<number, PlayerDetail>())
  const selection = parseSelection(value)
  const playerId = selection.kind === 'player' ? selection.id : null

  useEffect(() => {
    setError(null)
    if (playerId === null) return
    const cached = cache.current.get(playerId)
    if (cached) {
      setPlayer(cached)
      return
    }
    let cancelled = false
    api
      .getPlayer(jobId, playerId)
      .then((p) => {
        cache.current.set(playerId, p)
        if (!cancelled) setPlayer(p)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Could not load this player.')
      })
    return () => {
      cancelled = true
    }
  }, [jobId, playerId])

  let heatmap: Heatmap | undefined
  let track: PlayerDetail['track'] | null = null
  if (selection.kind === 'team') {
    heatmap = stats.heatmaps[selection.team]
  } else if (player?.player_id === selection.id) {
    heatmap = player.heatmap
    track = showTrack ? player.track : null
  }
  const label = options.find((o) => o.value === value)?.label ?? 'All players'
  const aspect = stats.video ? stats.video.width / stats.video.height : 16 / 9

  return (
    <section className="card stack">
      <div className="page-head">
        <h2>Where players spent their time</h2>
        <PlayerSelector options={options} value={value} onChange={setValue} />
      </div>
      {selection.kind === 'player' && (
        <label className="inline-check">
          <input type="checkbox" checked={showTrack} onChange={(e) => setShowTrack(e.target.checked)} />
          Show this player's path
        </label>
      )}
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      {heatmap ? (
        <HeatmapCanvas heatmap={heatmap} aspect={aspect} track={track} label={label} />
      ) : (
        !error && <p className="muted">Loading heatmap…</p>
      )}
      {player && selection.kind === 'player' && player.player_id === selection.id && (
        <p className="muted">
          #{player.player_id}: visible in {player.frames_visible} frames · {player.possession_pct}% possession ·
          moved {Number(player.distance_rel.toFixed(2))} × the frame diagonal
        </p>
      )}
    </section>
  )
}
