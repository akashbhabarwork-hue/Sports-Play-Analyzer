import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { displayName, initials } from '../logic/user'
import { useAuth } from '../useAuth'
import { LogoutIcon, SettingsIcon } from './icons'

export function Avatar({ name, email }: { name: string | null; email: string | null }) {
  return (
    <span className="avatar" aria-hidden="true">
      {initials({ name, email })}
    </span>
  )
}

/** Avatar button + dropdown (name, email, Settings, Log out). Esc / outside click closes it. */
export function UserMenu() {
  const { state, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  if (state.status !== 'authenticated') return null
  const { me } = state

  async function onLogout() {
    setOpen(false)
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="user-menu" ref={ref}>
      <button
        type="button"
        className="user-button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <Avatar name={me.name} email={me.email} />
        <span className="user-button-name">{displayName(me)}</span>
      </button>
      {open && (
        <div className="menu" role="menu">
          <div className="menu-head">
            <strong>{displayName(me)}</strong>
            {me.email && <span className="muted">{me.email}</span>}
          </div>
          <Link role="menuitem" className="menu-item" to="/app/settings" onClick={() => setOpen(false)}>
            <SettingsIcon size={18} /> Settings
          </Link>
          <button role="menuitem" type="button" className="menu-item" onClick={onLogout}>
            <LogoutIcon size={18} /> Log out
          </button>
        </div>
      )}
    </div>
  )
}
