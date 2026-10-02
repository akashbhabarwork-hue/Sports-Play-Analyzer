import type { Me } from '../types'

type Who = Pick<Me, 'name' | 'email'>

export function initials({ name, email }: Who): string {
  const words = (name ?? '').trim().split(/\s+/).filter(Boolean)
  if (words.length > 0) {
    const first = words[0][0]
    const last = words.length > 1 ? words[words.length - 1][0] : ''
    return (first + last).toUpperCase()
  }
  if (email) return email[0].toUpperCase()
  return '?'
}

export function displayName({ name, email }: Who): string {
  return name?.trim() || email || 'Signed in'
}
