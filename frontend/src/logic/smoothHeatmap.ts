// Smooth heatmap rendering (pure): bilinear upscaling of the backend's count grid and a
// blue → green → yellow → red ramp, fully transparent where the count is 0 (brief).
import type { Heatmap, Sport } from '../types'

type RGBA = [number, number, number, number]

const STOPS: [number, [number, number, number]][] = [
  [0, [37, 99, 235]], // blue
  [1 / 3, [34, 197, 94]], // green
  [2 / 3, [250, 204, 21]], // yellow
  [1, [220, 38, 38]], // red
]

export function rampColour(t: number): RGBA {
  const v = Math.max(0, Math.min(1, t))
  if (v === 0) return [0, 0, 0, 0]
  let i = 0
  while (i < STOPS.length - 2 && v > STOPS[i + 1][0]) i += 1
  const [t0, c0] = STOPS[i]
  const [t1, c1] = STOPS[i + 1]
  const f = (v - t0) / (t1 - t0)
  const mix = (k: number) => Math.round(c0[k] + (c1[k] - c0[k]) * f)
  // Opacity fades in from 0 (not a jump to 35 %), so interpolated edges don't draw a box.
  return [mix(0), mix(1), mix(2), Math.round(255 * 0.9 * Math.min(1, v / 0.3))]
}

/** Value 0..1 (count / max) at normalised point (u, v), interpolating between cell centres. */
export function sampleBilinear(hm: Heatmap, u: number, v: number): number {
  if (hm.max <= 0) return 0
  const gx = Math.min(Math.max(u * hm.w - 0.5, 0), hm.w - 1)
  const gy = Math.min(Math.max(v * hm.h - 0.5, 0), hm.h - 1)
  const x0 = Math.floor(gx)
  const y0 = Math.floor(gy)
  const x1 = Math.min(x0 + 1, hm.w - 1)
  const y1 = Math.min(y0 + 1, hm.h - 1)
  const fx = gx - x0
  const fy = gy - y0
  const at = (x: number, y: number) => hm.counts[y * hm.w + x] / hm.max
  const top = at(x0, y0) * (1 - fx) + at(x1, y0) * fx
  const bottom = at(x0, y1) * (1 - fx) + at(x1, y1) * fx
  return top * (1 - fy) + bottom * fy
}

/** RGBA pixel buffer (width × height × 4) ready for an ImageData. */
export function renderHeatmap(hm: Heatmap, width: number, height: number): Uint8ClampedArray {
  const out = new Uint8ClampedArray(width * height * 4)
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const c = rampColour(sampleBilinear(hm, (x + 0.5) / width, (y + 0.5) / height))
      out.set(c, (y * width + x) * 4)
    }
  }
  return out
}

/** Field markings in unit coordinates (x, y in 0..1; circle/arc radius in units of height). */
export type Shape =
  | { kind: 'rect'; x: number; y: number; w: number; h: number }
  | { kind: 'line'; x1: number; y1: number; x2: number; y2: number }
  | { kind: 'circle'; cx: number; cy: number; r: number }
  | { kind: 'arc'; cx: number; cy: number; r: number; start: number; end: number }

export function fieldShapes(sport: Sport): Shape[] {
  const outline: Shape = { kind: 'rect', x: 0.03, y: 0.04, w: 0.94, h: 0.92 }
  const halfway: Shape = { kind: 'line', x1: 0.5, y1: 0.04, x2: 0.5, y2: 0.96 }
  if (sport === 'basketball') {
    return [
      outline,
      halfway,
      { kind: 'circle', cx: 0.5, cy: 0.5, r: 0.12 },
      { kind: 'rect', x: 0.03, y: 0.34, w: 0.17, h: 0.32 }, // keys
      { kind: 'rect', x: 0.8, y: 0.34, w: 0.17, h: 0.32 },
      { kind: 'arc', cx: 0.07, cy: 0.5, r: 0.42, start: -Math.PI / 2, end: Math.PI / 2 }, // 3-pt
      { kind: 'arc', cx: 0.93, cy: 0.5, r: 0.42, start: Math.PI / 2, end: (3 * Math.PI) / 2 },
      { kind: 'circle', cx: 0.07, cy: 0.5, r: 0.025 }, // hoops
      { kind: 'circle', cx: 0.93, cy: 0.5, r: 0.025 },
    ]
  }
  return [
    outline,
    halfway,
    { kind: 'circle', cx: 0.5, cy: 0.5, r: 0.16 },
    { kind: 'rect', x: 0.03, y: 0.25, w: 0.14, h: 0.5 }, // penalty boxes
    { kind: 'rect', x: 0.83, y: 0.25, w: 0.14, h: 0.5 },
    { kind: 'rect', x: 0.03, y: 0.38, w: 0.05, h: 0.24 }, // six-yard boxes
    { kind: 'rect', x: 0.92, y: 0.38, w: 0.05, h: 0.24 },
  ]
}
