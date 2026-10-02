import type { Stats } from '../types'

export interface ErrorHelp {
  title: string
  action: { label: string; to: string } | null
}

const UPLOAD = '/app/new'

// Titles for the failure codes the worker records (D-026). The server's own message is shown
// underneath; this adds a headline and the obvious next step.
const HELP: Record<string, ErrorHelp> = {
  YOUTUBE_BLOCKED: {
    title: 'YouTube blocked our server from downloading this video',
    action: { label: 'Upload the file instead', to: UPLOAD },
  },
  DOWNLOAD_FAILED: {
    title: 'We could not download this video',
    action: { label: 'Upload the file instead', to: UPLOAD },
  },
  URL_NOT_ALLOWED: { title: 'Only YouTube links are supported', action: { label: 'Try another link', to: `${UPLOAD}?tab=url` } },
  CORRUPT_FILE: { title: "We couldn't read this video", action: { label: 'Upload another file', to: UPLOAD } },
  DECODE_ERROR: { title: "We couldn't decode this video", action: { label: 'Upload another file', to: UPLOAD } },
  UNSUPPORTED_FORMAT: { title: 'This file type is not supported', action: { label: 'Upload another file', to: UPLOAD } },
  DURATION_EXCEEDED: { title: 'This video is longer than 60 seconds', action: { label: 'Upload a shorter clip', to: UPLOAD } },
  MODEL_ERROR: { title: 'The player detector is unavailable', action: null },
  WORKER_CRASHED: { title: 'Processing failed several times', action: { label: 'Submit it again', to: UPLOAD } },
}

export function errorHelp(code: string): ErrorHelp {
  return HELP[code] ?? { title: 'The analysis failed', action: { label: 'Try another video', to: UPLOAD } }
}

export interface Summary {
  playersTracked: number
  ballVisiblePct: number
  topPossession: { playerId: number; pct: number } | null
  totalDistanceRel: number
}

export function summarize(stats: Stats): Summary {
  const top = stats.possession.by_player.reduce<{ playerId: number; pct: number } | null>(
    (best, p) => (!best || p.pct > best.pct ? { playerId: p.player_id, pct: p.pct } : best),
    null,
  )
  const total = stats.players.reduce((sum, p) => sum + p.distance_rel, 0)
  return {
    playersTracked: stats.players_tracked,
    ballVisiblePct: stats.ball_visible_pct,
    topPossession: top,
    totalDistanceRel: Math.round(total * 100) / 100,
  }
}
