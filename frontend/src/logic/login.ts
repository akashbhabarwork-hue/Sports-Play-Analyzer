// Messages for /login?error=… (the backend redirects there when Google login fails).
// Only known codes map to text; anything else gets a generic line, never the raw query value.
const MESSAGES: Record<string, string> = {
  oauth_failed: 'Google sign-in did not complete. Please try again.',
  cancelled: 'Sign-in was cancelled. Continue with Google when you are ready.',
  login_unavailable: 'Google sign-in is not available on this server right now. Please try again later.',
  server_error: 'We could not finish signing you in. Please try again in a moment.',
}

export function loginErrorMessage(search: string): string | null {
  const code = new URLSearchParams(search).get('error')
  if (!code) return null
  return MESSAGES[code] ?? 'Sign-in failed. Please try again.'
}
