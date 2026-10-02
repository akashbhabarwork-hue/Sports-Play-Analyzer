// Mirrors backend/app/entrypoints/schemas.py and the stats contract (D-028, sports-metrics).

export type JobStatus = 'queued' | 'processing' | 'succeeded' | 'failed'

export interface Me {
  id: string
  email: string | null
  name: string | null
  avatar_url: string | null
}

export interface JobError {
  code: string
  message: string | null
}

export type Sport = 'football' | 'basketball'

// Worker stages in order (backend core/pipeline.STAGES, T-087); "fetching" only for URL jobs.
export type Stage = 'fetching' | 'analysing' | 'computing' | 'rendering' | 'saving'

export interface JobSummary {
  id: string
  title: string | null
  sport: Sport
  source_type: 'upload' | 'url'
  original_filename: string | null
  source_url: string | null
  duration_s: number | null
  size_bytes: number | null
  thumbnail_url: string | null
  status: JobStatus
  progress: number // 0-100; 100 only once succeeded
  stage: Stage | null
  error: JobError | null
  created_at: string
  finished_at: string | null
}

export interface VideoInfo {
  source_type: 'upload' | 'url'
  original_filename: string | null
  source_url: string | null
  duration_s: number | null
}

export interface JobDetail extends JobSummary {
  started_at: string | null
  attempts: number
  video: VideoInfo | null
}

export interface JobAccepted {
  job_id: string
  status: JobStatus
}

export interface Heatmap {
  w: number
  h: number
  counts: number[] // row-major: h rows of w cells
  max: number
}

export type Team = 'A' | 'B' | 'unknown'

export interface PlayerStats {
  player_id: number
  team: Team | null
  distance_px: number
  distance_rel: number // distance / frame diagonal
  frames_visible: number
  possession_pct: number
}

export interface Stats {
  job_id: string
  players_tracked: number
  ball_visible_pct: number
  possession: {
    by_player: { player_id: number; pct: number }[]
    by_team: Record<string, number>
    unassigned_pct: number
  }
  players: PlayerStats[]
  teams: Record<string, { players: number[]; distance_rel_total: number }>
  heatmaps: Record<string, Heatmap>
  video?: { duration_s: number; width: number; height: number; sample_fps: number }
  config?: Record<string, unknown> // effective settings the result was produced with (D-026)
}

export interface PlayerDetail extends PlayerStats {
  track: [number, number, number][] // [t_s, nx, ny] feet position, normalised 0-1
  heatmap: Heatmap
}
