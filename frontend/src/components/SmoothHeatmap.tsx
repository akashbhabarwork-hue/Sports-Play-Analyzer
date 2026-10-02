import { useEffect, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { fieldShapes, renderHeatmap } from '../logic/smoothHeatmap'
import type { Heatmap, Sport } from '../types'

interface Props {
  heatmap: Heatmap
  sport: Sport
  aspect: number // frame width / height, so the map lines up with the video
  track?: [number, number, number][] | null
  label: string
}

const RENDER_WIDTH = 320 // heat is rendered small, then scaled up smoothly by the browser
const SURFACE: Record<Sport, string> = { football: '#1e4a2c', basketball: '#5b3f26' }

export function SmoothHeatmap({ heatmap, sport, aspect, track, label }: Props) {
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
    canvas.width = Math.round(width * dpr)
    canvas.height = Math.round(height * dpr)
    canvas.style.height = `${height}px`
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

    ctx.fillStyle = SURFACE[sport]
    ctx.fillRect(0, 0, width, height)

    // Heat: small RGBA buffer → offscreen canvas → scaled draw with smoothing.
    const rh = Math.max(1, Math.round(RENDER_WIDTH / aspect))
    const off = document.createElement('canvas')
    off.width = RENDER_WIDTH
    off.height = rh
    off.getContext('2d')?.putImageData(new ImageData(renderHeatmap(heatmap, RENDER_WIDTH, rh), RENDER_WIDTH, rh), 0, 0)
    ctx.imageSmoothingEnabled = true
    ctx.imageSmoothingQuality = 'high'
    ctx.drawImage(off, 0, 0, width, height)

    // Field markings on top so they stay readable through the heat.
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.6)'
    ctx.lineWidth = 2
    for (const s of fieldShapes(sport)) {
      ctx.beginPath()
      if (s.kind === 'rect') ctx.rect(s.x * width, s.y * height, s.w * width, s.h * height)
      else if (s.kind === 'line') {
        ctx.moveTo(s.x1 * width, s.y1 * height)
        ctx.lineTo(s.x2 * width, s.y2 * height)
      } else if (s.kind === 'circle') ctx.arc(s.cx * width, s.cy * height, s.r * height, 0, Math.PI * 2)
      else ctx.arc(s.cx * width, s.cy * height, s.r * height, s.start, s.end)
      ctx.stroke()
    }

    if (track && track.length > 1) {
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.95)'
      ctx.lineWidth = 2.5
      ctx.lineJoin = 'round'
      ctx.beginPath()
      track.forEach(([, nx, ny], i) => (i === 0 ? ctx.moveTo(nx * width, ny * height) : ctx.lineTo(nx * width, ny * height)))
      ctx.stroke()
      const [, sx, sy] = track[0]
      const [, ex, ey] = track[track.length - 1]
      ctx.fillStyle = '#ffffff'
      ctx.beginPath()
      ctx.arc(sx * width, sy * height, 4, 0, Math.PI * 2)
      ctx.fill()
      ctx.fillStyle = '#f59e0b'
      ctx.beginPath()
      ctx.arc(ex * width, ey * height, 5, 0, Math.PI * 2)
      ctx.fill()
    }
  }, [heatmap, sport, aspect, track, width])

  return (
    <figure className="heat" style={{ '--aspect': aspect } as CSSProperties}>
      <div ref={wrapRef} className="heat-wrap">
        <canvas ref={canvasRef} role="img" aria-label={`Heatmap: ${label}`} />
      </div>
      <figcaption className="heat-legend">
        <span>less time</span>
        <span className="heat-ramp" aria-hidden="true" />
        <span>more time</span>
        {track && track.length > 1 && (
          <span className="path-key">
            <span className="dot start" aria-hidden="true" /> start <span className="dot end" aria-hidden="true" /> end
          </span>
        )}
      </figcaption>
    </figure>
  )
}
