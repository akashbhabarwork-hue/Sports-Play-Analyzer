import { Link } from 'react-router-dom'
import { brand } from '../assets/brand'

export function NotFoundPage({ what = 'Page' }: { what?: string }) {
  return (
    <section className="card center">
      <img className="empty-art" src={brand.tactics} alt="" width={96} height={96} />
      <h1>{what} not found</h1>
      <p className="muted">It may have been removed, or it belongs to another account.</p>
      <Link to="/app">Back to your analyses</Link>
    </section>
  )
}
