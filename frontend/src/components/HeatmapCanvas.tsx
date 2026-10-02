import { useEffect, useRef, useState } from 'react'
import { cellRects, heatColour, trackPoints } from '../logic/heatmap'
import type { Heatmap } from '../types'

interface Props {
  heatmap: Heatmap
  aspect: number // frame width / height, so cells line up with the video
  track?: [number, number, number][] | null
  label: string
}

/** Heat grid over a neutral pitch/court outline, sized to its container (crisp on HiDPI). */
export function HeatmapCanvas({ heatmap, aspect, track, label }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [width, setWidth] = useState(0)

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const observer = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)))
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx || width === 0) return
    const height = Math.round(width / aspect)
    const dpr = window.devicePixelRatio || 1
    canvas.width = width * dpr
    canvas.height = height * dpr
    canvas.style.height = `${height}px`
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

    // Neutral playing surface: works for a football pitch or a basketball court.
    ctx.fillStyle = '#2f5d3a'
    ctx.fillRect(0, 0, width, height)
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.55)'
    ctx.lineWidth = 2
    const m = 6
    ctx.strokeRect(m, m, width - 2 * m, height - 2 * m)
    ctx.beginPath()
    ctx.moveTo(width / 2, m)
    ctx.lineTo(width / 2, height - m)
    ctx.stroke()
    ctx.beginPath()
    ctx.arc(width / 2, height / 2, Math.min(width, height) * 0.12, 0, Math.PI * 2)
    ctx.stroke()

    for (const cell of cellRects(heatmap, width, height)) {
      ctx.fillStyle = heatColour(cell.value)
      ctx.fillRect(cell.x, cell.y, cell.w + 0.5, cell.h + 0.5) // +0.5: no hairline gaps
    }

    if (track && track.length > 1) {
      const points = trackPoints(track, width, height)
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.9)'
      ctx.lineWidth = 2
      ctx.beginPath()
      points.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)))
      ctx.stroke()
    }
  }, [heatmap, aspect, track, width])

  return (
    <figure className="heatmap">
      <div ref={wrapRef}>
        <canvas ref={canvasRef} role="img" aria-label={`Heatmap: ${label}`} style={{ width: '100%' }} />
      </div>
      <figcaption className="legend">
        <span>less</span>
        <span className="legend-ramp" aria-hidden="true" />
        <span>more time here</span>
      </figcaption>
    </figure>
  )
}
