// Session state for the SPA. The session itself is an httpOnly cookie the page can't read;
// we learn who is logged in by asking GET /api/me (401 = not logged in).
import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { ApiError, api } from './api'
import { signOut } from './logic/session'
import { AuthContext, useAuth } from './useAuth'
import type { AuthState } from './useAuth'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    api
      .me()
      .then((me) => !cancelled && setState({ status: 'authenticated', me }))
      .catch((err: unknown) => {
        if (cancelled) return
        // 401 = no session. Any other failure also shows the login page rather than a
        // half-working app; the login button simply retries.
        if (!(err instanceof ApiError && err.status === 401)) console.error(err)
        setState({ status: 'anonymous' })
      })
    return () => {
      cancelled = true
    }
  }, [])

  const logout = useCallback(
    () => signOut(api.logout, () => setState({ status: 'anonymous' })),
    [],
  )

  return <AuthContext.Provider value={{ state, logout }}>{children}</AuthContext.Provider>
}

/** Renders children only for a logged-in user; otherwise sends them to the login page. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { state } = useAuth()
  const location = useLocation()
  if (state.status === 'loading') return <p className="muted center">Loading…</p>
  if (state.status === 'anonymous') {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <>{children}</>
}
