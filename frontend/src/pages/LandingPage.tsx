import type { CSSProperties, ReactNode } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { brand } from '../assets/brand'
import {
  ArrowRightIcon,
  ArrowUpIcon,
  ChartIcon,
  GoogleIcon,
  RunnerIcon,
  ScanUsersIcon,
  ShieldLockIcon,
  VideoPlayIcon,
} from '../components/icons'
import { Logo, LogoMark } from '../components/Logo'
import { useAuth } from '../useAuth'
import './public.css'

const FEATURES = [
  { icon: ScanUsersIcon, tint: 'violet', title: 'Player & ball tracking', text: 'Every player gets a stable ID across the clip; the ball is tracked when visible.' },
  { icon: ChartIcon, tint: 'rose', title: 'Position heatmaps', text: 'See where each player and each team spent their time.' },
  { icon: VideoPlayIcon, tint: 'sky', title: 'Possession estimate', text: 'Who was closest to the ball, frame by frame, summed per player and team.' },
  { icon: ShieldLockIcon, tint: 'violet', title: 'Private to your account', text: 'Your clips and results are only visible to you.' },
]

/** Small illustrations for the three steps (decorative). */
function StepArt({ kind }: { kind: 'upload' | 'analyse' | 'results' }) {
  const art: Record<typeof kind, ReactNode> = {
    upload: (
      <>
        <span className="art-card">
          <span className="art-play" />
        </span>
        <span className="art-badge">
          <ArrowUpIcon size={16} />
        </span>
      </>
    ),
    analyse: (
      <span className="art-scan">
        <RunnerIcon size={34} />
      </span>
    ),
    results: (
      <>
        <span className="art-card">
          <ChartIcon size={30} />
        </span>
        <span className="art-badge">
          <span className="art-play small" />
        </span>
      </>
    ),
  }
  return (
    <span className={`step-art step-art-${kind}`} aria-hidden="true">
      {art[kind]}
    </span>
  )
}

const STEPS = [
  { kind: 'upload' as const, title: 'Upload a clip or paste a link', text: 'Up to 60 seconds of football or basketball footage.' },
  { kind: 'analyse' as const, title: 'We analyse it in the background', text: 'Players are detected, tracked and split into teams by kit colour.' },
  { kind: 'results' as const, title: 'Review the results', text: 'An annotated video, key stats and heatmaps for every player.' },
]

export function LandingPage() {
  const { state } = useAuth()
  if (state.status === 'authenticated') return <Navigate to="/app" replace />

  // The banner is set through CSS variables (CSSOM, allowed by our CSP) so the stylesheet can
  // pick the small file on phones.
  const heroStyle = {
    '--hero-img': `url(${brand.heroBanner})`,
    '--hero-img-sm': `url(${brand.heroBanner960})`,
  } as CSSProperties

  return (
    <div className="public">
      <header className="hero" style={heroStyle}>
        <nav className="hero-nav" aria-label="Site">
          <Logo onDark height={48} />
          <div className="hero-links">
            <a href="#features">Features</a>
            <a href="#how">How it works</a>
            <Link to="/login" className="btn btn-hero-outline">
              Sign in
            </Link>
          </div>
        </nav>
        <div className="hero-body">
          <div className="hero-copy">
            <div className="pills">
              <span className="pill">Football</span>
              <span className="pill">Basketball</span>
            </div>
            <h1>Turn Game Clips into Tactical Insights</h1>
            <p className="hero-sub">
              Upload a short football or basketball clip and get player tracking, possession,
              heatmaps and key stats, with an annotated video you can scrub through.
            </p>
            <a className="btn btn-primary btn-lg" href="/auth/login">
              <span className="google-chip">
                <GoogleIcon />
              </span>
              Get started with Google
            </a>
            <p className="hero-note">Free to try · clips up to 60 s · private by default</p>
          </div>
        </div>
      </header>

      <main className="landing-main">
        <section id="features" className="section">
          <h2 className="section-title">
            What you <span className="accent">get</span>
          </h2>
          <ul className="feature-grid">
            {FEATURES.map(({ icon: Icon, tint, title, text }) => (
              <li key={title} className={`card feature tint-${tint}`}>
                <span className="feature-icon">
                  <Icon size={26} />
                </span>
                <h3>{title}</h3>
                <p className="muted">{text}</p>
              </li>
            ))}
          </ul>
        </section>

        <section id="how" className="section">
          <h2 className="section-title">
            How it <span className="accent">works</span>
          </h2>
          <ol className="steps">
            {STEPS.map(({ kind, title, text }, i) => (
              <li key={title} className="step">
                <span className="step-num">{i + 1}</span>
                <StepArt kind={kind} />
                <div className="step-text">
                  <h3>{title}</h3>
                  <p className="muted">{text}</p>
                </div>
                {i < STEPS.length - 1 && (
                  <span className="step-arrow" aria-hidden="true">
                    <ArrowRightIcon size={18} />
                  </span>
                )}
              </li>
            ))}
          </ol>
        </section>
      </main>

      <footer className="public-footer muted">
        <span className="footer-mark">
          <LogoMark size={26} />
        </span>
        <span>
          <strong className="footer-name">Sports Play Analyzer</strong>: pretrained detection, no training on your videos.
        </span>
        <span className="footer-rule" aria-hidden="true" />
      </footer>
    </div>
  )
}
