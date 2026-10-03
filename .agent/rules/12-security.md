---
trigger: model_decision
description: Apply when touching authentication, OAuth, sessions, cookies, authorization checks, file uploads, URL fetching, yt-dlp, ffmpeg, subprocess calls, CORS, rate limiting, security headers, secrets or environment variables.
---

# Security rules

Deep guides: skills `oauth-pkce-sessions`, `ssrf-safe-url-fetch`, `upload-validation`,
`web-security-baseline`.

## AuthN
- Google OAuth 2.0 Authorization Code + PKCE (S256) via Authlib. Never hand-roll token exchange,
  state or PKCE. Verify `state`, `nonce`, ID token signature/audience via Authlib.
- Session = random 32-byte token in cookie `__Host-sid` (`HttpOnly; Secure; SameSite=Lax; Path=/`,
  no Domain). Store only `sha256(token)` in `sessions`. 7-day absolute expiry, rotate on login,
  delete on logout. Local dev over http uses cookie `sid` with Secure off (env `COOKIE_SECURE=false`).
- State-changing requests from the SPA send `X-Requested-With: fetch`; reject cross-site
  unsafe methods (Origin check against `APP_ORIGIN`) as CSRF defence on top of SameSite=Lax.

## AuthZ
- `current_user` dependency on every `/api/*` route except `/health` and `/auth/*`.
- Ownership enforced in SQL (`WHERE id = :id AND user_id = :uid`). Missing or foreign → 404
  (never 403, do not reveal existence). Applies to jobs, stats, players, video, heatmaps.
- Annotated video served via ownership-checked endpoint (streams or 302 to short-lived presigned URL
  ≤5 min). Blob keys are never guessable-only protection.

## SSRF (URL path)
- Scheme `https` only; host allowlist: `youtube.com, www.youtube.com, m.youtube.com, youtu.be`;
  media hosts allowlist `*.googlevideo.com`. No userinfo, no custom ports.
- Resolve DNS and reject if ANY address is private, loopback, link-local, multicast, reserved,
  unspecified, CGNAT (100.64/10) or IPv4-mapped private IPv6.
- Follow redirects manually (max 5), re-validating host + IP at every hop.
- Hard duration cap: reject metadata duration > 60 s before download; also enforce `-t 60` on
  ffmpeg and a byte cap while streaming the download.

## Subprocess
- `subprocess.run([...], shell=False, timeout=…, check=False)`; arguments are list items; user
  values never become flags (put `--` before URLs where the tool supports it). No `os.system`.

## Uploads
- Stream to a temp file in chunks, abort at 100 MB (413). Sniff magic bytes (MP4/MOV/WebM/MKV/AVI)
 , never trust extension or Content-Type. `ffprobe` validates it decodes and duration ≤ 60 s.
- Temp files in a per-request temp dir, removed in `finally`.

## Platform basics
- Rate limit submit endpoints (e.g. 10/min/user + 30/hour/user) → 429 with `Retry-After`.
- CORS: same-origin by default; if enabled, allow only `APP_ORIGIN`, credentials true, no `*`.
- Security headers middleware: CSP (self; media/img from self + blob host), `X-Content-Type-Options:
  nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: DENY`,
  `Strict-Transport-Security` (prod only), `Permissions-Policy` minimal.
- Secrets only via env; `.env.example` placeholders; GitHub Environment secrets for CD.
