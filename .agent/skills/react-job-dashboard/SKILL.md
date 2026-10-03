---
name: react-job-dashboard
description: Builds the React + Vite + TypeScript frontend for the analyzer, login page, upload/URL submit form with client-side pre-checks, live-polling job list with progress, job detail with annotated video player, stats cards and a canvas heatmap with player selector and team toggle, plus error states (corrupt file, YouTube blocked, rate limit, not found). Use for any UI work.
---

# React job dashboard

## Structure
```
frontend/src/
  api.ts            # fetch wrapper, types, error envelope → ApiError(code, message, status)
  types.ts          # Job, JobStats, PlayerDetail, Heatmap (mirror backend schemas)
  hooks/usePolling.ts
  pages/LoginPage.tsx  SubmitPage.tsx  JobsPage.tsx  JobDetailPage.tsx
  components/UploadForm.tsx  UrlForm.tsx  JobRow.tsx  ProgressBar.tsx  VideoPlayer.tsx
             StatsCards.tsx  HeatmapCanvas.tsx  PlayerSelector.tsx  ErrorBanner.tsx
  App.tsx (routes + auth guard using GET /api/me)
```
Vite dev server proxies `/api` and `/auth` to `http://localhost:8000` (same-origin cookies in dev).
Production: FastAPI serves `frontend/dist` with an SPA fallback to `index.html` for non-API paths.

## api.ts essentials
```ts
export class ApiError extends Error { constructor(public status: number, public code: string, message: string) { super(message); } }
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, { credentials: "same-origin", ...init,
    headers: { "X-Requested-With": "fetch", ...(init.headers || {}) } });
  if (res.status === 401) { window.location.assign("/login"); throw new ApiError(401, "UNAUTHORIZED", "Please log in"); }
  if (!res.ok) { const b = await res.json().catch(() => null);
    throw new ApiError(res.status, b?.error?.code ?? "HTTP_" + res.status, b?.error?.message ?? "Something went wrong"); }
  return res.status === 204 ? (undefined as T) : res.json();
}
```
Upload uses `FormData` (don't set Content-Type manually). Show upload progress with
`XMLHttpRequest.upload.onprogress` if time allows (SHOULD).

## Pages
- **Login**: product name, one "Continue with Google" button → `window.location = "/auth/login"`.
- **Submit**: tabs Upload | YouTube URL. Pre-checks: size ≤100 MB; duration via hidden `<video>`
  `loadedmetadata` ≤60 s (UX only). On 202 → navigate to `/jobs/:id`.
- **Jobs**: table: created, source, status chip, progress bar, error message. `usePolling(fetchJobs,
  2000, enabled = some job active)`. Pause polling when `document.hidden`.
- **Job detail**: status header; if processing → progress + stage; if failed → ErrorBanner with the
  server message and, for `YOUTUBE_BLOCKED`, an "Upload the file instead" button; if succeeded →
  `<video controls playsInline src="/api/jobs/{id}/video">`, StatsCards (players tracked, ball
  visible %, top possession, total distance), HeatmapCanvas + PlayerSelector (`All players`,
  `Team A`, `Team B`, then `#1…#N` sorted by id with distance shown).

## HeatmapCanvas
Draw a neutral pitch/court outline (simple rectangle + centre line/circle), then for each cell
`alpha = counts[i] / max` fill with a sequential colour (e.g. transparent → yellow → red).
Canvas sized by container width with devicePixelRatio scaling; legend "fewer ↔ more time here".
Optionally overlay the player's track polyline (toggle).

## Error & empty states (acceptance #2 and #3 depend on them)
- Upload 415/422 → inline message from server under the form.
- Job failed → red banner, code in small monospace, human message big.
- 404 on job detail → "Job not found" page with link back (this is what user B sees).
- 429 → "Too many submissions, try again in a minute."

## Checks before finishing
`npm run lint && npm run typecheck && npm run build`: all green. Manual pass through acceptance
flow in the browser; note it in the devlog.
