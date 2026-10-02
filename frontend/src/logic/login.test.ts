import { describe, expect, it } from 'vitest'
import { loginErrorMessage } from './login'

describe('loginErrorMessage', () => {
  it('explains a failed Google login', () => {
    expect(loginErrorMessage('?error=oauth_failed')).toMatch(/Google sign-in did not complete/)
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
