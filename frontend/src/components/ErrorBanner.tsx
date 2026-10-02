import { Link } from 'react-router-dom'
import { errorHelp } from '../logic/results'
import type { JobError } from '../types'

export function ErrorBanner({ error }: { error: JobError }) {
  const help = errorHelp(error.code)
  return (
    <div className="banner-error" role="alert">
      <h2>{help.title}</h2>
      {error.message && <p>{error.message}</p>}
      <p className="muted">
        Error code <code>{error.code}</code>
      </p>
      {help.action && (
        <Link className="button" to={help.action.to}>
          {help.action.label}
        </Link>
      )}
    </div>
  )
}
