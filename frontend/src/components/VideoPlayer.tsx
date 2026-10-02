import { useState } from 'react'

/** The annotated video. The API streams it with Range support (seekable) or redirects to a
 *  short-lived storage URL; either way a plain <video src> works. */
export function VideoPlayer({ src }: { src: string }) {
  const [failed, setFailed] = useState(false)
  if (failed) {
    return (
      <p className="alert" role="alert">
        The annotated video could not be loaded. Reload the page to try again.
      </p>
    )
  }
  return (
    <video
      className="player"
      src={src}
      controls
      playsInline
      preload="metadata"
      onError={() => setFailed(true)}
    >
      Your browser cannot play this video.
    </video>
  )
}
