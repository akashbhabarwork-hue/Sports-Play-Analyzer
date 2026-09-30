---
name: web-security-baseline
description: Adds platform security basics to the FastAPI app — per-user rate limiting on submit endpoints, restricted CORS, security headers (CSP, HSTS, nosniff, frame-deny), Origin-check CSRF defence, safe error responses and secret handling. Use when configuring middleware, headers, CORS, rate limits or env secrets.
---

# Web security baseline

## Rate limiting
- Submit endpoints (`POST /api/jobs/upload`, `POST /api/jobs/url`): `RATE_LIMIT_SUBMIT` default
  `"10/minute;30/hour"` keyed by `user.id` (fallback client IP).
- Simple option: `slowapi` (in-memory) — fine for one web instance; state it in the ADR.
  Stronger option (if time): Postgres fixed-window counter table so multiple instances share limits.
- Response: 429 + `Retry-After` + envelope `{"error":{"code":"RATE_LIMITED","message":"Too many
  submissions, try again in a minute."}}`.
- Also cap concurrent active jobs per user (e.g. 3 queued/processing) → 429 `TOO_MANY_ACTIVE_JOBS`.

## CORS
SPA is served from the same origin, so CORS middleware is **off** by default. If `CORS_ORIGINS`
is set (dev with Vite on :5173), allow exactly those origins, `allow_credentials=True`, methods
`GET,POST`, headers `Content-Type,X-Requested-With`. Never `*` with credentials.
(In dev prefer Vite's proxy to the API so it's same-origin anyway.)

## Security headers (function middleware)
```python
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)   # dict built once from Settings
    return response
```
FastAPI HTTP middleware must be `async def`; it's infrastructure glue, one of the documented async
exceptions (see rule 10). Headers:
- `Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; media-src 'self' <BLOB_PUBLIC_ORIGIN>; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self' https://accounts.google.com`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` only when `APP_ENV=prod`.
- `Cache-Control: no-store` on `/api/*` and `/auth/*`.

## CSRF defence in depth
For POST/PUT/PATCH/DELETE on `/api/*` and `/auth/logout`: require `Origin` (or `Referer`) to equal
`APP_ORIGIN`, and header `X-Requested-With: fetch`. Else 403 `CSRF_REJECTED`.

## Errors
Single `AppError` handler → envelope. Generic handler for `Exception` → 500 `INTERNAL` with a
request id; the stack trace only goes to logs.

## Secrets
- `.env.example` lists every variable with placeholder/dev values and a comment.
- Prod secrets in GitHub Environment `production` + host secret store (`fly secrets set`).
- Pre-commit or CI step: `gitleaks` (pinned) scanning the repo history.
- Never log headers wholesale (cookies!). Redact `Authorization`, `Cookie`, `Set-Cookie`.

## Tests
- Headers present on `/health` and `/`.
- 11th submit within a minute → 429.
- POST with foreign Origin → 403.
