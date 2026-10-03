// Brand art cropped from the owner's asset sheet (transparent WebP, ≤ 320 px). Decorative:
// use with alt="" next to real text, never as the only label. Vite fingerprints the files.
import ballBasketball from './ball-basketball.webp'
import ballFootball from './ball-football.webp'
import chart from './chart.webp'
import courtBasketball from './court-basketball.webp'
import heatmapPitch from './heatmap-pitch.webp'
import iconError from './icon-error.webp'
import iconRunner from './icon-runner.webp'
import iconTarget from './icon-target.webp'
import iconUpload from './icon-upload.webp'
import logoMark from './logo-mark.webp'
import pitchFootball from './pitch-football.webp'
import playerBasketball from './player-basketball.webp'
import playerFootball from './player-football.webp'
import tactics from './tactics.webp'

export const brand = {
  ballBasketball,
  ballFootball,
  chart,
  courtBasketball,
  heatmapPitch,
  iconError,
  iconRunner,
  iconTarget,
  iconUpload,
  logoMark,
  pitchFootball,
  playerBasketball,
  playerFootball,
  tactics,
}

type Sport = 'football' | 'basketball'

export const sportArt: Record<Sport, { ball: string; field: string; player: string }> = {
  football: { ball: ballFootball, field: pitchFootball, player: playerFootball },
  basketball: { ball: ballBasketball, field: courtBasketball, player: playerBasketball },
}

/** Art for a job's sport; unknown or missing sport falls back to football. */
export function artFor(sport: string | null | undefined) {
  return sportArt[sport === 'basketball' ? 'basketball' : 'football']
}
