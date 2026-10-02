// Messages for /login?error=… (the backend redirects there when Google login fails).
// Only known codes map to text; anything else gets a generic line, never the raw query value.
const MESSAGES: Record<string, string> = {
  oauth_failed: 'Google sign-in did not complete. Please try again.',
}

export function loginErrorMessage(search: string): string | null {
  const code = new URLSearchParams(search).get('error')
  if (!code) return null
  return MESSAGES[code] ?? 'Sign-in failed. Please try again.'
}
