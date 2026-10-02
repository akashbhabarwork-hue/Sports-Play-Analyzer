import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../useAuth'
import { loginErrorMessage } from '../logic/login'

export function LoginPage() {
  const { state } = useAuth()
  const location = useLocation()
  const error = loginErrorMessage(location.search)

  if (state.status === 'authenticated') return <Navigate to="/app" replace />

  return (
    <main className="login">
      <div className="card login-card">
        <h1>Sports Play Analyzer</h1>
        <p className="muted">
          Upload a football or basketball clip (up to 60 s) or paste a YouTube link. We track
          the players and the ball and show distance, possession and heatmaps.
        </p>
        {error && (
          <p className="alert" role="alert">
            {error}
          </p>
        )}
        {/* Full-page navigation: the OAuth flow is server-side (Authorization Code + PKCE). */}
        <a className="button primary" href="/auth/login">
          Continue with Google
        </a>
      </div>
    </main>
  )
}
