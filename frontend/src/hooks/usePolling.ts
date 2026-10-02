import { useEffect, useRef } from 'react'
import { createPoller } from '../logic/poller'

/** Calls `task` every `intervalMs` while `enabled`, paused while the tab is hidden. */
export function usePolling(task: () => Promise<unknown>, intervalMs: number, enabled: boolean) {
  const latest = useRef(task)
  useEffect(() => {
    latest.current = task
  })

  useEffect(() => {
    if (!enabled) return
    const poller = createPoller(() => latest.current(), intervalMs, () => document.hidden)
    const onVisibility = () => poller.visibilityChanged()
    document.addEventListener('visibilitychange', onVisibility)
    poller.start()
    return () => {
      poller.stop()
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [enabled, intervalMs])
}
