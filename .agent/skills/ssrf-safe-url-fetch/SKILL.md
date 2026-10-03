---
name: ssrf-safe-url-fetch
description: Safely fetches YouTube videos server-side with yt-dlp and an SSRF-guarded HTTP downloader, host allowlist, DNS resolution with private/internal IP blocking, manual redirect re-validation, duration and byte caps, argument-array subprocess calls, and graceful YOUTUBE_BLOCKED errors with upload fallback. Use for the URL submission path.
---

# SSRF-safe YouTube fetch

## Threats (name them in the review)
User-supplied URLs can make our server call internal services (`169.254.169.254` cloud metadata,
`localhost:5432`, `10.x` admin panels), via direct IPs, DNS names that resolve privately, or
redirects. Also: command injection via crafted URLs, and resource abuse via huge/long videos.

## Layered defence
1. **Syntactic check at submit (pure, `core/url_rules.py`)**
   - `urllib.parse.urlsplit`; scheme must be `https`; no username/password; port None or 443.
   - Host (lower-cased, trailing dot stripped, IDNA-encoded) ∈
     `{"youtube.com","www.youtube.com","m.youtube.com","youtu.be"}`.
   - Extract/normalise the video id (11 chars `[A-Za-z0-9_-]`); rebuild a canonical URL
     `https://www.youtube.com/watch?v=<id>`: we never pass the raw user string onward.
   - Reject playlists/channels/shorts-with-params if you can't normalise → `URL_NOT_ALLOWED`.
2. **Network check at fetch time (`core/net_rules.py` pure + adapter resolves)**
```python
import ipaddress
def is_public_ip(value: str) -> bool:
    ip = ipaddress.ip_address(value)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast   # is_global excludes private, loopback,
                                                  # link-local, reserved, CGNAT 100.64/10
```
   Resolve with `socket.getaddrinfo(host, 443)`; reject if ANY result is non-public.
3. **Metadata via yt-dlp (argument array, restricted extractor)**
```python
cmd = ["yt-dlp", "--dump-single-json", "--no-playlist", "--no-warnings",
       "--use-extractors", "youtube",
       "-f", "b[height<=720][ext=mp4]/bv*[height<=720][ext=mp4]/b[height<=720]",
       "--", canonical_url]
if settings.ytdlp_proxy: cmd[1:1] = ["--proxy", settings.ytdlp_proxy]
if cookies_path: cmd[1:1] = ["--cookies", cookies_path]
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45, shell=False)
```
   ⚠ Verify every flag against the installed version (`yt-dlp --help`), flags change and AI
   often invents them. Log a correction in AI_USAGE.md if one was wrong.
   - `duration` > `MAX_VIDEO_SECONDS` → `DURATION_EXCEEDED` (clear message with actual length).
   - `is_live` true → reject. Missing duration → reject.
   - Media URL = `info["url"]` (or first of `requested_formats`); headers = `info["http_headers"]`.
4. **Download with our own client (`adapters/safe_http_fetcher.py`)**
   - `httpx.Client(follow_redirects=False, timeout=httpx.Timeout(10, read=30))`.
   - Loop max 5 hops: validate scheme https, host matches media allowlist
     (`*.googlevideo.com`, `*.youtube.com`), resolve + `is_public_ip` for all addresses, then GET
     with `stream=True`; on 3xx take `Location` (resolve relative with `urljoin`) and repeat.
   - Stream chunks to a temp file; abort at `MAX_UPLOAD_MB`.
   - Then `ffprobe` the file and still apply the 60 s cap; ffmpeg decode also uses `-t 60`.
5. **Residual risk (ADR):** DNS rebinding between our check and httpx's connect. Mitigated because
   both allowlisted domains are Google-controlled (attacker can't change their DNS). Full fix =
   connect to the vetted IP with SNI/Host pinning, listed under "more time".

## YouTube blocking datacenter IPs (required in ADR)
Symptoms in yt-dlp stderr: "Sign in to confirm you’re not a bot", HTTP Error 403/429,
"Video unavailable" from cloud IPs while it works locally. Map to:
`UpstreamBlockedError(code="YOUTUBE_BLOCKED", message="YouTube blocked our server from downloading
this video. Please download the clip and upload it instead.")` → job `failed`; UI shows an
"Upload instead" button.

Mitigations (optional, env-driven, never committed):
- `YTDLP_COOKIES_B64`: base64 Netscape cookies file from a throwaway account; worker writes it to a
  0600 temp file per job and deletes it afterwards.
- `YTDLP_PROXY`: residential/egress proxy URL.
- Keep yt-dlp updated (pin, but bump often), YouTube changes break old versions.
**Test the URL path from the deployed host on day 1** (T-006 spike). Acceptance #1 uses a YouTube
URL, so if prod is blocked you need a mitigation or must explain the fallback clearly.

## Tests (unit, no network)
- URL rules: accept watch/shorts/youtu.be forms; reject http, ports, userinfo, `youtube.com.evil.io`,
  `evil.io/youtube.com`, IP hosts, playlist-only URLs.
- IP rules: 127.0.0.1, 10.0.0.1, 172.16.0.1, 192.168.1.1, 169.254.169.254, 100.64.0.1, 0.0.0.0,
  ::1, fc00::1, fe80::1, ::ffff:10.0.0.1 → blocked; 8.8.8.8, 142.250.0.1 → allowed.
- Redirect loop: fake transport returning 302 → `http://169.254.169.254/` → blocked.
- stderr classifier: sample bot-check message → YOUTUBE_BLOCKED.
