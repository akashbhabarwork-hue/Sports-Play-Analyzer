// A small polling scheduler (no React, so it can be tested with fake timers).
// - waits `intervalMs` *after* each request finishes, so requests never overlap;
// - a failed request just waits for the next tick;
// - while the tab is hidden it stops ticking; visibilityChanged() refreshes at once on return.

export interface Poller {
  start(): void
  stop(): void
  visibilityChanged(): void
}

export function createPoller(
  task: () => Promise<unknown>,
  intervalMs: number,
  isHidden: () => boolean,
): Poller {
  let timer: ReturnType<typeof setTimeout> | null = null
  let running = false
  let paused = false // a tick was skipped because the tab was hidden

  function schedule() {
    timer = setTimeout(tick, intervalMs)
  }

  async function tick() {
    timer = null
    if (!running) return
    if (isHidden()) {
      paused = true
      return
    }
    try {
      await task()
    } catch {
      // network blip or 5xx: try again on the next tick
    }
    if (running) schedule()
  }

  return {
    start() {
      if (running) return
      running = true
      paused = false
      schedule()
    },
    stop() {
      running = false
      if (timer !== null) clearTimeout(timer)
      timer = null
    },
    visibilityChanged() {
      if (!running || !paused || isHidden()) return
      paused = false
      void tick()
    },
  }
}
