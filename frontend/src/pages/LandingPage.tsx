import { Link, Navigate } from 'react-router-dom'
import { HeroArt } from '../components/HeroArt'
import { ChartIcon, GoogleIcon, ShieldIcon, UploadIcon, UsersIcon, VideoIcon } from '../components/icons'
import { Logo } from '../components/Logo'
import { useAuth } from '../useAuth'
import './public.css'

const FEATURES = [
  { icon: UsersIcon, title: 'Player & ball tracking', text: 'Every player gets a stable ID across the clip; the ball is tracked when visible.' },
  { icon: ChartIcon, title: 'Position heatmaps', text: 'See where each player and each team spent their time.' },
  { icon: VideoIcon, title: 'Possession estimate', text: 'Who was closest to the ball, frame by frame, summed per player and team.' },
  { icon: ShieldIcon, title: 'Private to your account', text: 'Your clips and results are only visible to you.' },
]

const STEPS = [
  { icon: UploadIcon, title: 'Upload a clip or paste a link', text: 'Up to 60 seconds of football or basketball footage.' },
  { icon: VideoIcon, title: 'We analyse it in the background', text: 'Players are detected, tracked and split into teams by kit colour.' },
  { icon: ChartIcon, title: 'Review the results', text: 'An annotated video, key stats and heatmaps for every player.' },
]

export function LandingPage() {
  const { state } = useAuth()
  if (state.status === 'authenticated') return <Navigate to="/app" replace />

  return (
    <div className="public">
      <header className="hero">
        <nav className="hero-nav" aria-label="Site">
          <Logo />
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
              heatmaps and key stats — with an annotated video you can scrub through.
            </p>
            <a className="btn btn-primary btn-lg" href="/auth/login">
              <span className="google-chip">
                <GoogleIcon />
              </span>
              Get started with Google
            </a>
            <p className="hero-note">Free to try · clips up to 60 s · private by default</p>
          </div>
          <HeroArt />
        </div>
      </header>

      <main>
        <section id="features" className="section">
          <h2 className="section-title">What you get</h2>
          <ul className="feature-grid">
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <li key={title} className="card feature">
                <span className="feature-icon">
                  <Icon />
                </span>
                <h3>{title}</h3>
                <p className="muted">{text}</p>
              </li>
            ))}
          </ul>
        </section>

        <section id="how" className="section">
          <h2 className="section-title">How it works</h2>
          <ol className="steps">
            {STEPS.map(({ icon: Icon, title, text }, i) => (
              <li key={title} className="card step">
                <span className="step-num">{i + 1}</span>
                <Icon />
                <h3>{title}</h3>
                <p className="muted">{text}</p>
              </li>
            ))}
          </ol>
        </section>
      </main>

      <footer className="public-footer muted">
        <Logo compact /> Sports Play Analyzer — pretrained detection, no training on your videos.
      </footer>
    </div>
  )
}
