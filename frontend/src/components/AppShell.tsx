import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import './shell.css'
import { CloseIcon, GridIcon, MenuIcon, PlusIcon, SettingsIcon, ShieldIcon } from './icons'
import { Logo } from './Logo'
import { UserMenu } from './UserMenu'

const NAV = [
  { to: '/app', label: 'My videos', icon: GridIcon, end: true },
  { to: '/app/new', label: 'New analysis', icon: PlusIcon, end: false },
  { to: '/app/settings', label: 'Settings', icon: SettingsIcon, end: false },
]

/** Signed-in layout: sidebar (≥ 900 px) or top bar + drawer (< 900 px), user menu top-right. */
export function AppShell() {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const { pathname } = useLocation()

  useEffect(() => setDrawerOpen(false), [pathname]) // navigating closes the drawer

  useEffect(() => {
    if (!drawerOpen) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setDrawerOpen(false)
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [drawerOpen])

  return (
    <div className="app">
      <aside id="sidebar" className={drawerOpen ? 'sidebar open' : 'sidebar'} aria-label="Main navigation">
        <div className="sidebar-head">
          <NavLink to="/app" end className="sidebar-logo">
            <Logo />
          </NavLink>
          <button type="button" className="icon-btn drawer-close" aria-label="Close menu" onClick={() => setDrawerOpen(false)}>
            <CloseIcon />
          </button>
        </div>
        <nav className="sidebar-nav">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className="nav-item">
              <Icon /> {label}
            </NavLink>
          ))}
        </nav>
        <p className="sidebar-foot muted">
          <ShieldIcon size={16} /> Your videos are private to your account.
        </p>
      </aside>
      {drawerOpen && <div className="backdrop" onClick={() => setDrawerOpen(false)} />}

      <div className="main">
        <header className="topbar">
          <button
            type="button"
            className="icon-btn menu-btn"
            aria-label="Open menu"
            aria-controls="sidebar"
            aria-expanded={drawerOpen}
            onClick={() => setDrawerOpen(true)}
          >
            <MenuIcon />
          </button>
          <span className="topbar-logo">
            <Logo />
          </span>
          <div className="topbar-spacer" />
          <UserMenu />
        </header>
        <main className="page">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
