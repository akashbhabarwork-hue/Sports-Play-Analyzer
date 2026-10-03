import type { Stats } from '../types'
import { teamsPresent } from './insights'

export interface AiStep {
  label: string // what the AI did
  detail: string // with what / how much, taken from the stats only
}

const MODEL_NAMES: Record<string, string> = { yolox_s: 'YOLOX-S' }

/** The "how this was analysed" strip on the results page. Every number comes from the job's
 *  stats (no invented figures); a step is left out when the stats don't say. */
export function aiSteps(stats: Stats): AiStep[] {
  const config = (stats.config ?? {}) as { detector?: { model?: string }; sample_fps?: number }
  const model = config.detector?.model
  const fps = stats.video?.sample_fps ?? config.sample_fps
  const frames = stats.video?.frames_analysed
  const teams = teamsPresent(stats).length

  const steps: AiStep[] = [
    { label: 'Detected', detail: `players and ball with ${MODEL_NAMES[model ?? ''] ?? model ?? 'YOLOX-S'}` },
  ]
  if (frames != null) {
    steps.push({ label: 'Analysed', detail: `${frames} frames${fps ? ` at ${fps} fps` : ''}` })
  }
  steps.push({
    label: 'Tracked',
    detail: `${stats.players_tracked} ${stats.players_tracked === 1 ? 'player' : 'players'} with stable IDs`,
  })
  steps.push({
    label: 'Teams',
    detail: teams >= 2 ? 'split by jersey colour' : 'kits too similar to split',
  })
  steps.push({ label: 'Ball', detail: `visible in ${stats.ball_visible_pct}% of frames` })
  return steps
}
