import { useState } from 'react'
import { SparkleIcon } from './icons'

/** The annotated video. The API streams it with Range support (seekable) or redirects to a
 *  short-lived storage URL; either way a plain <video src> works. Once it loads, a single scan
 *  sweep and an "AI annotated" badge mark it as the analysed output (no motion if the user
 *  prefers reduced motion). */
export function VideoPlayer({ src }: { src: string }) {
  const [failed, setFailed] = useState(false)
  const [loaded, setLoaded] = useState(false)
  if (failed) {
    return (
      <p className="alert" role="alert">
        The annotated video could not be loaded. Reload the page to try again.
      </p>
    )
  }
  return (
    <div className={loaded ? 'player-frame loaded' : 'player-frame'}>
      <video
        className="player"
        src={src}
        controls
        playsInline
        preload="metadata"
        onLoadedData={() => setLoaded(true)}
        onError={() => setFailed(true)}
      >
        Your browser cannot play this video.
      </video>
      <span className="ai-badge">
        <SparkleIcon size={14} /> AI annotated
      </span>
      <span className="scan-sweep" aria-hidden="true" />
    </div>
  )
}
