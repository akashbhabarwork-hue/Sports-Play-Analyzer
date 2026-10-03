import { describe, expect, it } from 'vitest'
import type { Stats } from '../types'
import { aiSteps } from './aiSummary'

const base = {
  players_tracked: 13,
  ball_visible_pct: 42.5,
  possession: { by_player: [], by_team: {}, unassigned_pct: 0 },
  players: [],
  teams: { A: { players: [1], distance_rel_total: 1 }, B: { players: [2], distance_rel_total: 1 } },
  heatmaps: {},
  video: { duration_s: 8, width: 1280, height: 720, sample_fps: 5, frames_analysed: 40 },
  config: { detector: { model: 'yolox_s' } },
} as unknown as Stats

describe('aiSteps', () => {
  it('describes the pipeline with numbers from the stats', () => {
    expect(aiSteps(base)).toEqual([
      { label: 'Detected', detail: 'players and ball with YOLOX-S' },
      { label: 'Analysed', detail: '40 frames at 5 fps' },
      { label: 'Tracked', detail: '13 players with stable IDs' },
      { label: 'Teams', detail: 'split by jersey colour' },
      { label: 'Ball', detail: 'visible in 42.5% of frames' },
    ])
  })

  it('leaves out what the stats do not say and is honest about teams', () => {
    const old = { ...base, players_tracked: 1, teams: {}, video: undefined, config: undefined } as unknown as Stats
    const steps = aiSteps(old)
    expect(steps.map((s) => s.label)).not.toContain('Analysed')
    expect(steps.find((s) => s.label === 'Tracked')?.detail).toBe('1 player with stable IDs')
    expect(steps.find((s) => s.label === 'Teams')?.detail).toBe('kits too similar to split')
    expect(steps[0].detail).toBe('players and ball with YOLOX-S')
  })
})
