import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider, RequireAuth } from './auth'
import { AppShell } from './components/AppShell'
import { JobDetailPage } from './pages/JobDetailPage'
import { MyVideosPage } from './pages/MyVideosPage'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import { NewAnalysisPage } from './pages/NewAnalysisPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { SettingsPage } from './pages/SettingsPage'

// Public pages: `/` (landing) and `/login`. Signed-in pages live under /app/… because /jobs/…
// are API aliases (D-028). Old paths redirect so bookmarks keep working.
function RedirectKeepingQuery({ to }: { to: string }) {
  const { search } = useLocation()
  return <Navigate to={`${to}${search}`} replace />
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/app/login" element={<RedirectKeepingQuery to="/login" />} />
          <Route path="/app/submit" element={<RedirectKeepingQuery to="/app/new" />} />
          <Route
            path="/app"
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          >
            <Route index element={<MyVideosPage />} />
            <Route path="new" element={<NewAnalysisPage />} />
            <Route path="jobs/:jobId" element={<JobDetailPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
