# Loom script (5 min)

0:00–0:30  What it is + live URL, log in with Google.
0:30–1:45  Architecture (ADR diagram): web, Postgres queue, worker, storage; why each choice.
1:45–3:15  Data flow live: submit YouTube URL → job id instantly → progress → annotated video →
           player heatmap. Mention SKIP LOCKED + lease retry, streamed frames.
3:15–4:00  Security: PKCE via Authlib, httpOnly cookie, 404 for other users (show second account),
           SSRF layers, corrupt upload clean error.
4:00–4:45  One thing the AI got wrong: <from AI_USAGE.md> — how I caught it, the fix.
4:45–5:00  What I cut / next steps.
