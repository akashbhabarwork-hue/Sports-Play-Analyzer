import { useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ApiError, api } from '../api'
import { formatDateTime, formatDuration } from '../logic/format'
import { aiSteps } from '../logic/aiSummary'
import { keyMetrics, settingsNote, teamName, teamsPresent } from '../logic/insights'
import { jobTitle, sportLabel } from '../logic/videos'
import type { JobDetail, PlayerDetail, Stats } from '../types'
import { BackIcon, CheckIcon, CopyIcon, DownloadIcon, InfoIcon, SparkleIcon } from './icons'
import { PlayerStatsTable, TeamDot } from './PlayerStatsTable'
import { SmoothHeatmap } from './SmoothHeatmap'
import { StatusChip } from './StatusChip'
import { VideoPlayer } from './VideoPlayer'
import './results.css'

type Tab = 'overview' | 'players' | 'teams' | 'player'
const TABS: { id: Tab; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'players', label: 'Player stats' },
  { id: 'teams', label: 'Team heatmaps' },
  { id: 'player', label: 'Player heatmaps' },
]
const DISTANCE_HELP = 'Distance measured in frame-relative units: 1.0 ≈ one frame diagonal; camera movement affects this.'

export function ResultsView({ job, stats }: { job: JobDetail; stats: Stats }) {
  const [params, setParams] = useSearchParams()
  const tab = (TABS.find((t) => t.id === params.get('tab'))?.id ?? 'overview') as Tab
  const [copied, setCopied] = useState(false)
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({})
  const aspect = stats.video ? stats.video.width / stats.video.height : 16 / 9

  function go(next: Tab, player?: number) {
    const p: Record<string, string> = next === 'overview' ? {} : { tab: next }
    if (player != null) p.player = String(player)
    else if (next === 'player' && params.get('player')) p.player = params.get('player')!
    setParams(p, { replace: true })
  }

  function onTabKey(e: KeyboardEvent<HTMLButtonElement>) {
    const i = TABS.findIndex((t) => t.id === tab)
    const delta = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!delta) return
    e.preventDefault()
    const next = TABS[(i + delta + TABS.length) % TABS.length].id
    go(next)
    tabRefs.current[next]?.focus()
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard blocked: the address bar has the link */
    }
  }

  return (
    <section className="results">
      <Link to="/app" className="back-link">
        <BackIcon size={18} /> Back to dashboard
      </Link>
      <header className="page-header">
        <div>
          <div className="title-row">
            <h1 className="ellipsis">{jobTitle(job)}</h1>
            <StatusChip status={job.status} />
          </div>
          <p className="muted small">
            {sportLabel(job.sport)} · {formatDuration(job.duration_s)} · analysed {formatDateTime(job.finished_at ?? job.created_at)}
          </p>
        </div>
        <div className="header-actions">
          <a className="btn btn-secondary" href={api.videoUrl(job.id)} download={`${jobTitle(job)}-annotated.mp4`}>
            <DownloadIcon size={18} /> Download annotated video
          </a>
          <button type="button" className="btn btn-secondary" onClick={copyLink}>
            {copied ? <CheckIcon size={18} /> : <CopyIcon size={18} />} {copied ? 'Copied' : 'Copy link'}
          </button>
        </div>
      </header>

      <AiSummary stats={stats} />

      <div className="tabs" role="tablist" aria-label="Results">
        {TABS.map((t) => (
          <button key={t.id} ref={(el) => (tabRefs.current[t.id] = el)} type="button" role="tab" id={`rt-${t.id}`}
                  aria-selected={tab === t.id} aria-controls={`rp-${t.id}`} tabIndex={tab === t.id ? 0 : -1}
                  className={tab === t.id ? 'tab active' : 'tab'} onClick={() => go(t.id)} onKeyDown={onTabKey}>
            {t.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`rp-${tab}`} aria-labelledby={`rt-${tab}`} className="tab-panel">
        {tab === 'overview' && <Overview job={job} stats={stats} />}
        {tab === 'players' && <PlayerStatsTable players={stats.players} onOpen={(id) => go('player', id)} />}
        {tab === 'teams' && <TeamHeatmaps job={job} stats={stats} aspect={aspect} />}
        {tab === 'player' && <PlayerHeatmaps job={job} stats={stats} aspect={aspect} selected={Number(params.get('player')) || null}
                                             onSelect={(id) => go('player', id)} />}
      </div>
    </section>
  )
}

/** "AI analysis complete" strip: what the pipeline did, with numbers from this job's stats. */
function AiSummary({ stats }: { stats: Stats }) {
  return (
    <section className="ai-summary" aria-label="How this video was analysed">
      <div className="ai-summary-head">
        <span className="ai-orb" aria-hidden="true">
          <SparkleIcon size={18} />
        </span>
        <div>
          <strong>AI analysis complete</strong>
          <span className="muted small"> · computer vision on every sampled frame</span>
        </div>
      </div>
      <ol className="ai-steps">
        {aiSteps(stats).map((s) => (
          <li key={s.label}>
            <CheckIcon size={14} />
            <span className="ai-step-label">{s.label}</span>
            <span className="muted">{s.detail}</span>
          </li>
        ))}
      </ol>
    </section>
  )
}

function Overview({ job, stats }: { job: JobDetail; stats: Stats }) {
  const m = keyMetrics(stats)
  const teams = teamsPresent(stats)
  const note = settingsNote(stats)
  return (
    <div className="overview">
      <div className="overview-video">
        <VideoPlayer src={api.videoUrl(job.id)} />
        <ul className="legend" aria-label="Video legend">
          {teams.map((t) => (
            <li key={t}>
              <TeamDot team={t} /> {teamName(t)}
            </li>
          ))}
          <li>
            <span className="ball-dot" aria-hidden="true" /> Ball
          </li>
          {teams.length === 0 && <li className="muted">Teams couldn't be told apart in this clip, so boxes are grey.</li>}
        </ul>
      </div>

      <div className="metrics" aria-label="Key metrics">
        <h2 className="sr-only">Key metrics</h2>
        <div className="card metric">
          <span className="metric-label">Players tracked</span>
          <span className="metric-value num">{m.playersTracked}</span>
        </div>
        <div className="card metric">
          <span className="metric-label">Ball visible</span>
          <span className="metric-value num">{m.ballVisiblePct}%</span>
          <span className="muted small">of sampled frames</span>
        </div>
        <div className="card metric">
          <span className="metric-label">Possession split</span>
          {m.ballVisiblePct === 0 ? (
            // Possession is "who is nearest the ball": with no ball detected there is nothing to split.
            <p className="muted small">The ball wasn't detected in this clip, so there is no possession estimate.</p>
          ) : (
            <>
              <div className="split-bar" role="img"
                   aria-label={`Team A ${m.possession.A}%, Team B ${m.possession.B}%, unassigned ${m.possession.unassigned}%`}>
                <span className="seg-a" style={{ width: `${m.possession.A}%` }} />
                <span className="seg-b" style={{ width: `${m.possession.B}%` }} />
                <span className="seg-u" style={{ width: `${m.possession.unassigned}%` }} />
              </div>
              <dl className="split-key num">
                <div><dt><TeamDot team="A" /> Team A</dt><dd>{m.possession.A}%</dd></div>
                <div><dt><TeamDot team="B" /> Team B</dt><dd>{m.possession.B}%</dd></div>
                <div><dt><TeamDot team={null} /> Unassigned</dt><dd>{m.possession.unassigned}%</dd></div>
              </dl>
            </>
          )}
        </div>
        <div className="card metric">
          <span className="metric-label">
            Total distance per team
            <span className="info" tabIndex={0} title={DISTANCE_HELP} aria-label={DISTANCE_HELP}>
              <InfoIcon size={16} />
            </span>
          </span>
          <dl className="split-key num">
            <div><dt><TeamDot team="A" /> Team A</dt><dd>{m.distance.A.toFixed(2)}</dd></div>
            <div><dt><TeamDot team="B" /> Team B</dt><dd>{m.distance.B.toFixed(2)}</dd></div>
          </dl>
          <span className="muted small">frame-relative units</span>
        </div>
      </div>
      {note && <p className="footnote muted small">Analysis settings: {note}</p>}
    </div>
  )
}

function TeamHeatmaps({ job, stats, aspect }: { job: JobDetail; stats: Stats; aspect: number }) {
  const present = teamsPresent(stats)
  const options = [...present.map((t) => ({ id: t, label: teamName(t) })), { id: 'all', label: 'All players' }]
  const [which, setWhich] = useState<string>(present[0] ?? 'all')
  const heatmap = stats.heatmaps[which]
  return (
    <div className="card heat-card">
      <div className="heat-head">
        <h2>Where each team spent its time</h2>
        <div className="segmented small-seg" role="radiogroup" aria-label="Team">
          {options.map((o) => (
            <button key={o.id} type="button" role="radio" aria-checked={which === o.id}
                    className={which === o.id ? 'seg active' : 'seg'} onClick={() => setWhich(o.id)}>
              {o.id !== 'all' && <TeamDot team={o.id} />} {o.label}
            </button>
          ))}
        </div>
      </div>
      {present.length === 0 && <p className="muted small">Teams couldn't be told apart in this clip, so only “All players” is available.</p>}
      {heatmap ? <SmoothHeatmap heatmap={heatmap} sport={job.sport} aspect={aspect} label={options.find((o) => o.id === which)?.label ?? ''} />
               : <p className="muted">No heatmap for this selection.</p>}
    </div>
  )
}

function PlayerHeatmaps({ job, stats, aspect, selected, onSelect }: {
  job: JobDetail; stats: Stats; aspect: number; selected: number | null; onSelect: (id: number) => void
}) {
  const players = useMemo(() => [...stats.players].sort((a, b) => a.player_id - b.player_id), [stats.players])
  const playerId = selected ?? players[0]?.player_id ?? null
  const [showPath, setShowPath] = useState(true)
  const [detail, setDetail] = useState<PlayerDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const cache = useRef(new Map<number, PlayerDetail>())

  useEffect(() => {
    if (playerId == null) return
    setError(null)
    const hit = cache.current.get(playerId)
    if (hit) {
      setDetail(hit)
      return
    }
    let cancelled = false
    api.getPlayer(job.id, playerId)
      .then((p) => {
        cache.current.set(playerId, p)
        if (!cancelled) setDetail(p)
      })
      .catch((err: unknown) => !cancelled && setError(err instanceof ApiError ? err.message : 'Could not load this player.'))
    return () => {
      cancelled = true
    }
  }, [job.id, playerId])

  if (playerId == null) return <p className="muted">No players were tracked in this clip.</p>
  const current = detail?.player_id === playerId ? detail : null

  return (
    <div className="card heat-card">
      <div className="heat-head">
        <label className="field inline-field">
          <span className="field-label">Player</span>
          <select className="select" value={playerId} onChange={(e) => onSelect(Number(e.target.value))}>
            {players.map((p) => (
              <option key={p.player_id} value={p.player_id}>
                #{p.player_id} · {teamName(p.team)}
              </option>
            ))}
          </select>
        </label>
        <label className="check">
          <input type="checkbox" checked={showPath} onChange={(e) => setShowPath(e.target.checked)} /> Show movement path
        </label>
      </div>
      {error && <p className="alert" role="alert">{error}</p>}
      {current ? (
        <>
          <SmoothHeatmap heatmap={current.heatmap} sport={job.sport} aspect={aspect}
                         track={showPath ? current.track : null} label={`player ${current.player_id}`} />
          <dl className="player-summary num">
            <div><dt>Team</dt><dd><TeamDot team={current.team} /> {teamName(current.team)}</dd></div>
            <div><dt>Distance</dt><dd>{current.distance_rel.toFixed(2)} × frame</dd></div>
            <div><dt>Distance (px)</dt><dd>{Math.round(current.distance_px).toLocaleString()}</dd></div>
            <div><dt>Frames visible</dt><dd>{current.frames_visible}</dd></div>
            <div><dt>Possession</dt><dd>{current.possession_pct.toFixed(1)}%</dd></div>
          </dl>
        </>
      ) : (
        !error && <p className="muted">Loading player…</p>
      )}
    </div>
  )
}
