import { useNavigate } from 'react-router-dom'
import { Avatar } from '../components/UserMenu'
import { LogoutIcon, ShieldIcon } from '../components/icons'
import { displayName } from '../logic/user'
import { useAuth } from '../useAuth'

/** Account + logout only (brief): there are no user-editable settings yet. */
export function SettingsPage() {
  const { state, logout } = useAuth()
  const navigate = useNavigate()
  if (state.status !== 'authenticated') return null
  const { me } = state

  async function onLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <section className="settings">
      <header className="page-header">
        <h1>Settings</h1>
        <p className="muted">Your account.</p>
      </header>
      <div className="card settings-account">
        <Avatar name={me.name} email={me.email} />
        <div>
          <h2>{displayName(me)}</h2>
          {me.email && <p className="muted">{me.email}</p>}
          <p className="muted small">Signed in with Google</p>
        </div>
      </div>
      <div className="card settings-privacy">
        <ShieldIcon />
        <p>
          Your videos and results are only visible to this account. Anyone else who opens one of
          your links sees “Job not found”.
        </p>
      </div>
      <div>
        <button type="button" className="btn btn-secondary" onClick={onLogout}>
          <LogoutIcon size={18} /> Log out
        </button>
      </div>
    </section>
  )
}
