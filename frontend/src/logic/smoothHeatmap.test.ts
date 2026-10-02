import { describe, expect, it } from 'vitest'
import { fieldShapes, rampColour, renderHeatmap, sampleBilinear } from './smoothHeatmap'

describe('rampColour', () => {
  it('is fully transparent where nobody spent time', () => {
    expect(rampColour(0)[3]).toBe(0)
  })

  // Regression (S8b walkthrough): a jump from 0 to 35 % opacity outlined every blob with a box.
  it('fades in smoothly from zero instead of jumping', () => {
    expect(rampColour(0.01)[3]).toBeLessThan(15)
    expect(rampColour(0.15)[3]).toBeLessThan(rampColour(0.3)[3])
  })

  it('goes blue → green → yellow → red as time increases', () => {
    const [r0, , b0] = rampColour(0.01)
    const [, g1] = rampColour(0.34)
    const [r2, g2, b2] = rampColour(0.67)
    const [r3, g3] = rampColour(1)
    expect(b0).toBeGreaterThan(r0) // blue
    expect(g1).toBeGreaterThan(150) // green
    // yellow
    expect(r2).toBeGreaterThan(200)
    expect(g2).toBeGreaterThan(150)
    expect(b2).toBeLessThan(80)
    // red
    expect(r3).toBeGreaterThan(200)
    expect(g3).toBeLessThan(80)
    expect(rampColour(1)[3]).toBeGreaterThan(rampColour(0.2)[3]) // hotter = more opaque
  })
})

describe('sampleBilinear', () => {
  const hm = { w: 2, h: 1, counts: [0, 4], max: 4 }

  it('returns the cell value at cell centres', () => {
    expect(sampleBilinear(hm, 0.25, 0.5)).toBeCloseTo(0)
    expect(sampleBilinear(hm, 0.75, 0.5)).toBeCloseTo(1)
  })

  it('blends smoothly between cell centres', () => {
    expect(sampleBilinear(hm, 0.5, 0.5)).toBeCloseTo(0.5)
  })

  it('clamps at the edges', () => {
    expect(sampleBilinear(hm, 0, 0.5)).toBeCloseTo(0)
    expect(sampleBilinear(hm, 1, 0.5)).toBeCloseTo(1)
  })

  it('is zero everywhere for an empty heatmap', () => {
    expect(sampleBilinear({ w: 2, h: 2, counts: [0, 0, 0, 0], max: 0 }, 0.5, 0.5)).toBe(0)
  })
})

describe('renderHeatmap', () => {
  it('produces RGBA pixels with zero alpha far from any visit', () => {
    const hm = { w: 4, h: 1, counts: [0, 0, 0, 9], max: 9 }
    const px = renderHeatmap(hm, 8, 2)
    expect(px).toHaveLength(8 * 2 * 4)
    expect(px[3]).toBe(0) // left edge: nobody there
    expect(px[(7 * 4) + 3]).toBeGreaterThan(0) // right edge: hottest cell
  })
})

describe('fieldShapes', () => {
  it('draws a football pitch with penalty boxes and a basketball court with keys and hoops', () => {
    const pitch = fieldShapes('football')
    const court = fieldShapes('basketball')
    expect(pitch.some((s) => s.kind === 'circle')).toBe(true)
    expect(pitch.filter((s) => s.kind === 'rect')).toHaveLength(5) // outline + 2 boxes + 2 six-yard
    expect(court.filter((s) => s.kind === 'rect')).toHaveLength(3) // outline + 2 keys
    expect(court.filter((s) => s.kind === 'arc')).toHaveLength(2) // three-point arcs
  })

  it('keeps every shape inside the unit square', () => {
    for (const s of [...fieldShapes('football'), ...fieldShapes('basketball')]) {
      if (s.kind === 'rect') expect(s.x >= 0 && s.y >= 0 && s.x + s.w <= 1 && s.y + s.h <= 1).toBe(true)
    }
  })
})
