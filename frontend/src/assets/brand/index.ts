// Brand art (owner-supplied): logo in light/dark versions, the hero banner, and art cropped from
// the asset sheet. Transparent WebP except the banner. Images next to real text use alt="".
// Vite fingerprints every file.
import ballBasketball from './ball-basketball.webp'
import ballFootball from './ball-football.webp'
import courtBasketball from './court-basketball.webp'
import heroBanner960 from './hero-banner-960.webp'
import heroBanner from './hero-banner.webp'
import iconError from './icon-error.webp'
import logoDark from './logo-dark.webp'
import logoLight from './logo-light.webp'
import logoMark from './logo-mark.webp'
import pitchFootball from './pitch-football.webp'
import playerBasketball from './player-basketball.webp'
import playerFootball from './player-football.webp'
import tactics from './tactics.webp'

export const brand = {
  ballBasketball,
  ballFootball,
  courtBasketball,
  heroBanner,
  heroBanner960,
  iconError,
  logoDark, // wordmark with light text, for dark surfaces
  logoLight, // wordmark with dark text, for light surfaces
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
