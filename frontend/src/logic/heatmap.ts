import type { Heatmap, Stats } from '../types'

export interface CellRect {
  x: number
  y: number
  w: number
  h: number
  value: number // 0..1 = count / max
}

/** Grid cells (row-major `counts`, h rows × w columns) as canvas rectangles; empty cells skipped. */
export function cellRects(hm: Heatmap, width: number, height: number): CellRect[] {
  if (hm.max <= 0) return []
  const cw = width / hm.w
  const ch = height / hm.h
  const rects: CellRect[] = []
  hm.counts.forEach((count, i) => {
    if (count <= 0) return
    const col = i % hm.w
    const row = Math.floor(i / hm.w)
    rects.push({ x: col * cw, y: row * ch, w: cw, h: ch, value: count / hm.max })
  })
  return rects
}

/** Sequential ramp: nothing → transparent; little time → yellow; most time → strong red.
 *  Opacity starts at 0.55 so even rarely visited cells read as yellow on the green pitch
 *  (at 0.25 they blended into a muddy olive). */
export function heatColour(t: number): string {
  const v = Math.max(0, Math.min(1, t))
  if (v === 0) return 'rgba(0, 0, 0, 0)'
  const r = Math.round(255 - 40 * v)
  const g = Math.round(220 - 195 * v)
  const b = Math.round(28 * v)
  const a = (0.55 + 0.35 * v).toFixed(2)
  return `rgba(${r}, ${g}, ${b}, ${a})`
}

/** Track samples [t_s, nx, ny] (feet, normalised to the frame) → canvas points. */
export function trackPoints(
  track: [number, number, number][],
  width: number,
  height: number,
): [number, number][] {
  return track.map(([, nx, ny]) => [nx * width, ny * height])
}

export type Selection = { kind: 'team'; team: 'all' | 'A' | 'B' } | { kind: 'player'; id: number }

export interface Option {
  value: string
  label: string
}

const round2 = (n: number) => Number(n.toFixed(2))

export function selectorOptions(stats: Stats): Option[] {
  const options: Option[] = [{ value: 'all', label: 'All players' }]
  for (const team of ['A', 'B'] as const) {
    const members = stats.teams?.[team]?.players ?? []
    if (members.length > 0) options.push({ value: `team:${team}`, label: `Team ${team} (${members.length})` })
  }
  const players = [...stats.players].sort((a, b) => a.player_id - b.player_id)
  for (const p of players) {
    const team = p.team === 'A' || p.team === 'B' ? ` · Team ${p.team}` : ''
    options.push({
      value: `player:${p.player_id}`,
      label: `#${p.player_id}${team} · ${round2(p.distance_rel)} × frame`,
    })
  }
  return options
}

export function parseSelection(value: string): Selection {
  if (value === 'team:A' || value === 'team:B') return { kind: 'team', team: value.slice(5) as 'A' | 'B' }
  const match = /^player:(\d+)$/.exec(value)
  if (match) return { kind: 'player', id: Number(match[1]) }
  return { kind: 'team', team: 'all' }
}
