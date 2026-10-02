import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPoller } from './poller'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

const flush = () => vi.advanceTimersByTimeAsync(0)

describe('createPoller', () => {
  it('runs the task every interval after start', async () => {
    const task = vi.fn().mockResolvedValue(undefined)
    const poller = createPoller(task, 2000, () => false)
    poller.start()
    await vi.advanceTimersByTimeAsync(1999)
    expect(task).toHaveBeenCalledTimes(0)
    await vi.advanceTimersByTimeAsync(1)
    expect(task).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(4000)
    expect(task).toHaveBeenCalledTimes(3)
    poller.stop()
  })

  it('never overlaps: the next wait starts only after a slow request finishes', async () => {
    let finish!: () => void
    const task = vi.fn(() => new Promise<void>((r) => (finish = r)))
    const poller = createPoller(task, 2000, () => false)
    poller.start()
    await vi.advanceTimersByTimeAsync(2000)
    await vi.advanceTimersByTimeAsync(10_000) // request still in flight
    expect(task).toHaveBeenCalledTimes(1)
    finish()
    await flush()
    await vi.advanceTimersByTimeAsync(2000)
    expect(task).toHaveBeenCalledTimes(2)
    poller.stop()
  })

  it('keeps polling after a failed request', async () => {
    const task = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue(undefined)
    const poller = createPoller(task, 1000, () => false)
    poller.start()
    await vi.advanceTimersByTimeAsync(2000)
    expect(task).toHaveBeenCalledTimes(2)
    poller.stop()
  })

  it('stops for good: no tick after stop, even if a request was in flight', async () => {
    let finish!: () => void
    const task = vi.fn(() => new Promise<void>((r) => (finish = r)))
    const poller = createPoller(task, 1000, () => false)
    poller.start()
    await vi.advanceTimersByTimeAsync(1000)
    poller.stop()
    finish()
    await vi.advanceTimersByTimeAsync(10_000)
    expect(task).toHaveBeenCalledTimes(1)
  })

  it('pauses while the tab is hidden and refreshes as soon as it is visible again', async () => {
    let hidden = false
    const task = vi.fn().mockResolvedValue(undefined)
    const poller = createPoller(task, 1000, () => hidden)
    poller.start()
    hidden = true
    await vi.advanceTimersByTimeAsync(10_000)
    expect(task).toHaveBeenCalledTimes(0)
    hidden = false
    poller.visibilityChanged()
    await flush()
    expect(task).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1000)
    expect(task).toHaveBeenCalledTimes(2)
    poller.stop()
  })

  it('does not double-schedule when visibility flips while already running', async () => {
    const task = vi.fn().mockResolvedValue(undefined)
    const poller = createPoller(task, 1000, () => false)
    poller.start()
    poller.visibilityChanged() // visible → visible: no extra immediate run
    await vi.advanceTimersByTimeAsync(1000)
    expect(task).toHaveBeenCalledTimes(1)
    poller.stop()
  })
})
