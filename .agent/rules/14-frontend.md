---
trigger: glob
globs: frontend/**
---

# Frontend rules (React + Vite + TypeScript)

Deep guide: skill `react-job-dashboard`.

- TypeScript strict. No `any` without a comment. ESLint + `tsc --noEmit` must pass.
- One small API client module (`src/api.ts`) using `fetch` with `credentials: "same-origin"` and
  header `X-Requested-With: fetch`. Handle the `{error:{code,message}}` envelope everywhere; show
  `message` to the user.
- Never store tokens in localStorage/sessionStorage; auth is the httpOnly cookie only.
- Screens: Login, Submit (upload tab + URL tab), Job list (live status/progress), Job detail
  (annotated video, stats cards, heatmap with player selector + team toggle).
- Live status: poll `GET /api/jobs` every 2 s while any job is `queued|processing`; stop otherwise.
- Client-side pre-checks (size ≤100 MB, duration ≤60 s via `<video>` metadata) are UX only, the
  server is the authority.
- Heatmap: draw the grid on a `<canvas>` over a neutral pitch/court background; include a legend.
- Error states are first-class: corrupt file, YouTube blocked (show "Upload instead" button),
  rate limited, not found.
- Accessibility: labelled inputs, keyboard-usable selector, sufficient contrast.
- Keep dependencies minimal: react, react-dom, react-router-dom. No UI kit unless approved.
