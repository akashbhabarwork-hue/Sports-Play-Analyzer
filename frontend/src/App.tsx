import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider, RequireAuth } from './auth'
import { Layout } from './components/Layout'
import { JobDetailPage } from './pages/JobDetailPage'
import { JobsPage } from './pages/JobsPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { SubmitPage } from './pages/SubmitPage'
import './App.css'

// Pages live under /app/… because /jobs/… are API aliases (D-028).
function LegacyLoginRedirect() {
  const { search } = useLocation() // keep ?error=oauth_failed from the backend
  return <Navigate to={`/app/login${search}`} replace />
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Navigate to="/app" replace />} />
          <Route path="/login" element={<LegacyLoginRedirect />} />
          <Route path="/app/login" element={<LoginPage />} />
          <Route
            path="/app"
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route index element={<JobsPage />} />
            <Route path="submit" element={<SubmitPage />} />
            <Route path="jobs/:jobId" element={<JobDetailPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
