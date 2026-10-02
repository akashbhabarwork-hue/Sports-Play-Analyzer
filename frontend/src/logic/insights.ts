import type { PlayerStats, Stats } from '../types'

export type TeamId = 'A' | 'B'

const round2 = (n: number) => Math.round(n * 100) / 100

/** The Overview's key metrics, read straight from the stats JSON (nothing derived or guessed). */
export function keyMetrics(stats: Stats) {
  const byTeam = stats.possession.by_team ?? {}
  return {
    playersTracked: stats.players_tracked,
    ballVisiblePct: stats.ball_visible_pct,
    possession: { A: byTeam.A ?? 0, B: byTeam.B ?? 0, unassigned: stats.possession.unassigned_pct },
    distance: {
      A: round2(stats.teams?.A?.distance_rel_total ?? 0),
      B: round2(stats.teams?.B?.distance_rel_total ?? 0),
    },
  }
}

/** Teams that actually have players — the legend and toggles never show an empty team. */
export function teamsPresent(stats: Stats): TeamId[] {
  return (['A', 'B'] as const).filter((t) => (stats.teams?.[t]?.players?.length ?? 0) > 0)
}

type Config = {
  sample_fps?: number
  tracker?: { high_thresh?: number }
  detector?: { model?: string; input_size?: number; ball_min_score?: number }
}

/** "Sampled at 5 fps · YOLOX-S detector at 640 px · …" from stats.config (the result's own record). */
export function settingsNote(stats: Stats): string {
  const c = (stats.config ?? {}) as Config
  const parts: string[] = []
  if (c.sample_fps != null) parts.push(`Sampled at ${c.sample_fps} fps`)
  if (c.detector?.model && c.detector.input_size) {
    parts.push(`${c.detector.model.replace(/_/g, '-').toUpperCase()} detector at ${c.detector.input_size} px`)
  }
  if (c.tracker?.high_thresh != null) parts.push(`tracks start at confidence ≥ ${c.tracker.high_thresh}`)
  if (c.detector?.ball_min_score != null) parts.push(`ball confidence ≥ ${c.detector.ball_min_score}`)
  return parts.join(' · ')
}

export type SortKey = 'player_id' | 'team' | 'distance_rel' | 'distance_px' | 'frames_visible' | 'possession_pct'
export type SortDir = 'asc' | 'desc'

export function sortPlayers(players: PlayerStats[], key: SortKey, dir: SortDir): PlayerStats[] {
  const sign = dir === 'asc' ? 1 : -1
  return [...players].sort((a, b) => {
    const av = a[key] ?? ''
    const bv = b[key] ?? ''
    const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv))
    return cmp !== 0 ? sign * cmp : a.player_id - b.player_id
  })
}

export function teamName(team: string | null): string {
  return team === 'A' ? 'Team A' : team === 'B' ? 'Team B' : 'No team'
}
