import { describe, expect, it, vi } from 'vitest'
import { signOut } from './session'

describe('signOut', () => {
  it('clears the local session after the server confirms', async () => {
    const clear = vi.fn()
    await signOut(() => Promise.resolve(), clear)
    expect(clear).toHaveBeenCalledOnce()
  })

  // Regression (S8 preview walkthrough): a failing POST /auth/logout left the user on the page.
  it('still clears the local session when the logout request fails', async () => {
    const clear = vi.fn()
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    await expect(signOut(() => Promise.reject(new Error('500')), clear)).resolves.toBeUndefined()
    expect(clear).toHaveBeenCalledOnce()
    warn.mockRestore()
  })
})
