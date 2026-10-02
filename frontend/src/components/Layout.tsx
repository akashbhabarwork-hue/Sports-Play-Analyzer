import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../useAuth'

export function Layout() {
  const { state, logout } = useAuth()
  const navigate = useNavigate()
  const me = state.status === 'authenticated' ? state.me : null

  async function onLogout() {
    await logout()
    navigate('/app/login', { replace: true })
  }

  return (
    <div className="shell">
      <header className="topbar">
        <NavLink to="/app" end className="brand">
          Sports Play Analyzer
        </NavLink>
        <nav aria-label="Main">
          <NavLink to="/app" end>
            Jobs
          </NavLink>
          <NavLink to="/app/submit">New analysis</NavLink>
        </nav>
        <div className="user">
          {me && <span title={me.email ?? undefined}>{me.name ?? me.email ?? 'Signed in'}</span>}
          <button type="button" className="secondary" onClick={onLogout}>
            Log out
          </button>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}
