---
name: oauth-pkce-sessions
description: Implements Google OAuth 2.0 Authorization Code flow with PKCE using Authlib in FastAPI, plus secure server-side sessions in an httpOnly Secure SameSite cookie, current_user dependency, logout and per-user authorization (404 on foreign objects). Use for login, callback, sessions, cookies, CSRF or ownership checks.
---

# OAuth 2.0 + PKCE (Google, Authlib) and secure sessions

## Flow (explain like this in the review)
1. `/auth/login`: Authlib generates `state`, `nonce` and a PKCE `code_verifier`; sends the browser to
   Google with `code_challenge = BASE64URL(SHA256(verifier))`, method `S256`. The transient values
   live in Starlette's signed session cookie for a few minutes only.
2. Google redirects back to `/auth/callback?code&state`. Authlib checks `state`, exchanges the code
   **with the verifier**, validates the ID token (signature, `aud`, `iss`, `nonce`, expiry).
3. We upsert the user by (`provider='google'`, `sub`), create our own session: random 32 bytes →
   cookie; store `sha256(token)` + expiry in `sessions`. Clear the transient OAuth cookie data.
4. Every API request: read cookie → hash → lookup non-expired session → `User`. Else 401.

PKCE stops an intercepted authorization code from being redeemed by anyone who doesn't hold the
verifier. Server-side sessions let us revoke instantly (logout deletes the row), and httpOnly keeps
the token away from JavaScript (XSS can't steal it).

## Setup
- Google Cloud Console → OAuth client "Web application". Authorised redirect URIs:
  `http://localhost:8000/auth/callback` and `https://<prod-host>/auth/callback`.
- Env: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SESSION_SECRET` (for Starlette transient
  cookie), `APP_ORIGIN`, `COOKIE_SECURE`.
- Deps: `authlib`, `httpx`, `itsdangerous` (Starlette SessionMiddleware).

## Adapter sketch (verify Authlib API against installed version before use)
```python
# adapters/oauth_google.py
from authlib.integrations.starlette_client import OAuth

def build_google_oauth(client_id: str, client_secret: str) -> OAuth:
    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile", "code_challenge_method": "S256"},
    )
    return oauth
```
Note: Authlib's Starlette client is async (`await oauth.google.authorize_redirect(...)`,
`await oauth.google.authorize_access_token(request)`). These two routes are the single documented
exception to "sync routes": keep them `async def` and thin, they only call Authlib, then call the
sync `services.auth.login_user(...)` via `fastapi.concurrency.run_in_threadpool`. Record this as a
decision (D-xxx), it's a good review talking point.

`SessionMiddleware(secret_key=SESSION_SECRET, same_site="lax", https_only=COOKIE_SECURE,
max_age=600, session_cookie="oauth_tx")`, used ONLY for OAuth transaction data.

## Our session cookie
```python
COOKIE_NAME = "__Host-sid" if settings.cookie_secure else "sid"   # __Host- requires Secure
response.set_cookie(COOKIE_NAME, token, httponly=True, secure=settings.cookie_secure,
                    samesite="lax", path="/", max_age=7*24*3600)
```
- Token: `secrets.token_urlsafe(32)`; DB stores `hashlib.sha256(token.encode()).digest()`.
- Rotate on login (new token each login; delete old if present). Logout: delete row + expire cookie.
- `SameSite=Lax` is required (Strict would drop the cookie on the Google → callback redirect chain
  for the first navigation). Add Origin check for unsafe methods as CSRF defence in depth.

## current_user dependency
```python
def current_user(request: Request, c: Container = Depends(get_container)) -> User:
    token = request.cookies.get(c.settings.cookie_name)
    if not token: raise UnauthorizedError("Please log in")
    user = get_user_for_session(c.session_repo, token, now=c.clock.now())
    if user is None: raise UnauthorizedError("Session expired, please log in again")
    return user
```

## Ownership = 404
```python
def get_job_for_user(repo: JobRepo, job_id: UUID, user_id: UUID) -> Job:
    job = repo.get_for_user(job_id, user_id)   # SQL: WHERE id=:id AND user_id=:uid
    if job is None: raise NotFoundError("Job not found")
    return job
```
Invalid UUID in path → 404 as well (don't 422-leak format info on job ids, optional nicety).

## Second test user for acceptance #3
Reviewers log in with two Google accounts. While the OAuth consent screen is in "Testing" mode only
listed test users can log in → **publish the app to "In production"** (basic scopes openid/email/
profile need no verification) or you'll fail acceptance. Put this in the deploy checklist.

## Tests
- Callback happy path with Authlib mocked at the adapter boundary (never call Google).
- Missing/expired/garbage cookie → 401. Logout → subsequent request 401.
- IDOR: user B → 404 on every job-scoped endpoint.
