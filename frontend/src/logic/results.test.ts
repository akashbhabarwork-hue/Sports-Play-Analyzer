import { describe, expect, it } from 'vitest'
import type { Stats } from '../types'
import { errorHelp, summarize } from './results'

describe('errorHelp', () => {
  it('offers an upload when YouTube blocks the server', () => {
    const help = errorHelp('YOUTUBE_BLOCKED')
    expect(help.action).toEqual({ label: 'Upload the file instead', to: '/app/submit' })
    expect(help.title).toMatch(/YouTube/)
  })

  it('suggests re-exporting for unreadable files', () => {
    expect(errorHelp('CORRUPT_FILE').title).toMatch(/couldn't read/i)
    expect(errorHelp('DECODE_ERROR').action?.to).toBe('/app/submit')
  })

  it('has a calm generic fallback for codes it does not know', () => {
    const help = errorHelp('SOMETHING_NEW')
    expect(help.title).toBe('The analysis failed')
    expect(help.action).toEqual({ label: 'Try another video', to: '/app/submit' })
  })
})

const stats = {
  players_tracked: 3,
  ball_visible_pct: 42.5,
  possession: {
    by_player: [
      { player_id: 2, pct: 30 },
      { player_id: 5, pct: 55.5 },
    ],
    by_team: {},
    unassigned_pct: 14.5,
  },
  players: [
    { player_id: 2, distance_rel: 1.25 },
    { player_id: 5, distance_rel: 0.5 },
    { player_id: 7, distance_rel: 0.25 },
  ],
} as unknown as Stats

describe('summarize', () => {
  it('picks the four headline numbers for the stats cards', () => {
    expect(summarize(stats)).toEqual({
      playersTracked: 3,
      ballVisiblePct: 42.5,
      topPossession: { playerId: 5, pct: 55.5 },
      totalDistanceRel: 2,
    })
  })

  it('copes with a clip where nobody had the ball', () => {
    const quiet = { ...stats, possession: { ...stats.possession, by_player: [] } }
    expect(summarize(quiet).topPossession).toBeNull()
  })
})
