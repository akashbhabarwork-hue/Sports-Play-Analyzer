import { describe, expect, it } from 'vitest'
import type { Stats } from '../types'
import { cellRects, heatColour, parseSelection, selectorOptions, trackPoints } from './heatmap'

describe('cellRects', () => {
  const hm = { w: 4, h: 2, counts: [0, 2, 0, 0, 0, 0, 0, 4], max: 4 }

  it('maps row-major counts to canvas rectangles, skipping empty cells', () => {
    const rects = cellRects(hm, 400, 200)
    expect(rects).toEqual([
      { x: 100, y: 0, w: 100, h: 100, value: 0.5 },
      { x: 300, y: 100, w: 100, h: 100, value: 1 },
    ])
  })

  it('draws nothing for an empty heatmap', () => {
    expect(cellRects({ w: 2, h: 1, counts: [0, 0], max: 0 }, 100, 50)).toEqual([])
  })
})

describe('heatColour', () => {
  it('is transparent for no time and gets warmer and more opaque with more time', () => {
    expect(heatColour(0)).toBe('rgba(0, 0, 0, 0)')
    const alpha = (c: string) => Number(c.split(',')[3].replace(')', ''))
    const green = (c: string) => Number(c.split(',')[1])
    expect(alpha(heatColour(1))).toBeGreaterThan(alpha(heatColour(0.2)))
    expect(green(heatColour(1))).toBeLessThan(green(heatColour(0.2))) // yellow → red
  })

  it('clamps out-of-range values', () => {
    expect(heatColour(2)).toBe(heatColour(1))
    expect(heatColour(-1)).toBe(heatColour(0))
  })
})

describe('trackPoints', () => {
  it('turns normalised feet positions into canvas pixels', () => {
    expect(trackPoints([[0, 0.5, 1], [0.2, 0, 0]], 200, 100)).toEqual([[100, 100], [0, 0]])
  })
})

const stats = {
  players: [
    { player_id: 7, team: 'B', distance_rel: 0.4 },
    { player_id: 2, team: 'A', distance_rel: 1.234 },
    { player_id: 3, team: 'unknown', distance_rel: 0 },
  ],
  teams: { A: { players: [2] }, B: { players: [7] } },
} as unknown as Stats

describe('selectorOptions', () => {
  it('lists all, the teams that have players, then players by id with distance', () => {
    expect(selectorOptions(stats).map((o) => o.label)).toEqual([
      'All players',
      'Team A (1)',
      'Team B (1)',
      '#2 · Team A · 1.23 × frame',
      '#3 · 0 × frame',
      '#7 · Team B · 0.4 × frame',
    ])
  })

  it('leaves out teams with no players (kits too similar → everyone unknown)', () => {
    const noTeams = { ...stats, teams: { A: { players: [] }, B: { players: [] } } } as unknown as Stats
    expect(selectorOptions(noTeams).map((o) => o.value).slice(0, 2)).toEqual(['all', 'player:2'])
  })
})

describe('parseSelection', () => {
  it('round-trips option values', () => {
    expect(parseSelection('all')).toEqual({ kind: 'team', team: 'all' })
    expect(parseSelection('team:B')).toEqual({ kind: 'team', team: 'B' })
    expect(parseSelection('player:12')).toEqual({ kind: 'player', id: 12 })
  })

  it('falls back to everyone for anything unexpected', () => {
    expect(parseSelection('player:x')).toEqual({ kind: 'team', team: 'all' })
    expect(parseSelection('team:C')).toEqual({ kind: 'team', team: 'all' })
  })
})
