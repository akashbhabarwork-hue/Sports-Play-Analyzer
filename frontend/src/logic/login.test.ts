import { describe, expect, it } from 'vitest'
import { loginErrorMessage } from './login'

describe('loginErrorMessage', () => {
  it('explains a failed Google login', () => {
    expect(loginErrorMessage('?error=oauth_failed')).toMatch(/Google sign-in did not complete/)
  })

  it('explains every code the backend redirects with', () => {
    expect(loginErrorMessage('?error=cancelled')).toMatch(/cancelled/)
    expect(loginErrorMessage('?error=login_unavailable')).toMatch(/not available/)
    expect(loginErrorMessage('?error=server_error')).toMatch(/could not finish/)
  })

  it('says nothing without an error', () => {
    expect(loginErrorMessage('')).toBeNull()
  })

  it('never echoes arbitrary query text into the page', () => {
    expect(loginErrorMessage('?error=<script>alert(1)</script>')).toBe(
      'Sign-in failed. Please try again.',
    )
  })
})
