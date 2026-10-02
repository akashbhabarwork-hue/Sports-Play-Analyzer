import { describe, expect, it } from 'vitest'
import type { PlayerStats, Stats } from '../types'
import { keyMetrics, settingsNote, sortPlayers, teamsPresent } from './insights'

const stats = {
  players_tracked: 4,
  ball_visible_pct: 62.5,
  possession: { by_player: [], by_team: { A: 48.2, B: 31.8 }, unassigned_pct: 20 },
  players: [],
  teams: {
    A: { players: [1, 3], distance_rel_total: 1.234 },
    B: { players: [2], distance_rel_total: 0.5 },
  },
  heatmaps: {},
  config: {
    sample_fps: 5,
    tracker: { high_thresh: 0.5 },
    detector: { model: 'yolox_s', input_size: 640, ball_min_score: 0.15 },
  },
} as unknown as Stats

describe('keyMetrics', () => {
  it('takes possession and distance per team straight from the stats', () => {
    expect(keyMetrics(stats)).toEqual({
      playersTracked: 4,
      ballVisiblePct: 62.5,
      possession: { A: 48.2, B: 31.8, unassigned: 20 },
      distance: { A: 1.23, B: 0.5 },
    })
  })

  it('treats a team missing from the stats as 0, never invented', () => {
    const noB = { ...stats, possession: { ...stats.possession, by_team: { A: 80 } }, teams: { A: stats.teams.A } } as Stats
    expect(keyMetrics(noB).possession.B).toBe(0)
    expect(keyMetrics(noB).distance.B).toBe(0)
  })
})

describe('teamsPresent', () => {
  it('lists only teams that have players (no fake "Team B" legend)', () => {
    expect(teamsPresent(stats)).toEqual(['A', 'B'])
    expect(teamsPresent({ ...stats, teams: { A: { players: [], distance_rel_total: 0 }, B: { players: [], distance_rel_total: 0 } } } as unknown as Stats)).toEqual([])
  })
})

describe('settingsNote', () => {
  it('summarises the settings the result was produced with', () => {
    expect(settingsNote(stats)).toBe('Sampled at 5 fps · YOLOX-S detector at 640 px · tracks start at confidence ≥ 0.5 · ball confidence ≥ 0.15')
  })

  it('omits what the result does not record', () => {
    expect(settingsNote({ ...stats, config: { sample_fps: 5 } } as unknown as Stats)).toBe('Sampled at 5 fps')
    expect(settingsNote({ ...stats, config: undefined } as unknown as Stats)).toBe('')
  })
})

const p = (id: number, over: Partial<PlayerStats>): PlayerStats => ({
  player_id: id, team: 'A', distance_px: 0, distance_rel: 0, frames_visible: 0, possession_pct: 0, ...over,
})

describe('sortPlayers', () => {
  const players = [p(3, { distance_rel: 0.4, team: 'B' }), p(1, { distance_rel: 0.9 }), p(2, { distance_rel: 0.4 })]

  it('sorts by a numeric column, ties broken by player id', () => {
    expect(sortPlayers(players, 'distance_rel', 'desc').map((x) => x.player_id)).toEqual([1, 2, 3])
    expect(sortPlayers(players, 'distance_rel', 'asc').map((x) => x.player_id)).toEqual([2, 3, 1])
  })

  it('sorts by team as text and does not mutate the input', () => {
    const copy = [...players]
    expect(sortPlayers(players, 'team', 'asc').map((x) => x.team)).toEqual(['A', 'A', 'B'])
    expect(players).toEqual(copy)
  })
})
