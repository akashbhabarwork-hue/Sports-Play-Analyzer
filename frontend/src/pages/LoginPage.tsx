import { Link, Navigate, useLocation } from 'react-router-dom'
import { ClockIcon, GoogleIcon, GridIcon, ShieldIcon } from '../components/icons'
import { Logo } from '../components/Logo'
import { loginErrorMessage } from '../logic/login'
import { useAuth } from '../useAuth'
import './public.css'

export function LoginPage() {
  const { state } = useAuth()
  const location = useLocation()
  const error = loginErrorMessage(location.search)

  if (state.status === 'authenticated') return <Navigate to="/app" replace />

  return (
    <main className="signin">
      <div className="card signin-card">
        <Link to="/" className="signin-logo" aria-label="Sports Play Analyzer home">
          <Logo height={44} />
        </Link>
        <div>
          <h1>Sign in to continue</h1>
          <p className="muted">Use your Google account. We only read your name and email.</p>
        </div>
        {error && (
          <p className="alert" role="alert">
            {error}
          </p>
        )}
        {/* Full-page navigation: the OAuth flow is server-side (Authorization Code + PKCE). */}
        <a className="btn btn-google btn-block" href="/auth/login">
          <GoogleIcon /> Continue with Google
        </a>
        <ul className="reassure">
          <li>
            <ShieldIcon size={18} /> Your data stays private
          </li>
          <li>
            <ClockIcon size={18} /> Background processing
          </li>
          <li>
            <GridIcon size={18} /> All your analyses in one place
          </li>
        </ul>
      </div>
    </main>
  )
}
