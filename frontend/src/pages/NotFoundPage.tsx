import { Link } from 'react-router-dom'

export function NotFoundPage({ what = 'Page' }: { what?: string }) {
  return (
    <section className="card center">
      <h1>{what} not found</h1>
      <p className="muted">It may have been removed, or it belongs to another account.</p>
      <Link to="/app">Back to your analyses</Link>
    </section>
  )
}
