import { describe, expect, it } from 'vitest'
import { displayName, initials } from './user'

describe('initials', () => {
  it('uses the first letters of the first and last name', () => {
    expect(initials({ name: 'Alice Coach', email: 'a@example.com' })).toBe('AC')
    expect(initials({ name: '  maria   de la cruz ', email: null })).toBe('MC')
  })

  it('falls back to the email, then a neutral placeholder', () => {
    expect(initials({ name: null, email: 'bob@example.com' })).toBe('B')
    expect(initials({ name: '', email: null })).toBe('?')
  })
})

describe('displayName', () => {
  it('prefers the name, then the email', () => {
    expect(displayName({ name: 'Alice', email: 'a@x.com' })).toBe('Alice')
    expect(displayName({ name: null, email: 'a@x.com' })).toBe('a@x.com')
    expect(displayName({ name: null, email: null })).toBe('Signed in')
  })
})
