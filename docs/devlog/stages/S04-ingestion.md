# Stage S04 - Ingestion

**Dates:** 2026-10-02 → 2026-10-02 · **Tickets:** T-040, T-041, T-042, T-043

## What was built (plain English)
- One storage interface with two backends: a local folder for development and S3-compatible storage for production. Keys are validated, writes are atomic, and videos are shared through 5-minute signed links.
- File upload that judges the file by its content, cheapest check first: size before the body is parsed, then the file's magic bytes, then ffprobe for decodability, duration (≤ 60 s) and resolution. The temp folder is removed in every outcome.
- YouTube link submission that accepts only four exact YouTube hostnames over https, extracts the 11-character video id and rebuilds the URL itself; the request returns in milliseconds with no network call.
- The worker's fetch stage: yt-dlp only reports *what* to download; our own client downloads it, re-checking every redirect hop's host and every DNS answer, with byte and time caps. The downloaded file then goes through exactly the same checks as an upload.

## How it works now (data flow for this stage)
```mermaid
sequenceDiagram
  participant U as User
  participant A as API
  participant B as BlobStore
  participant DB as Postgres
  participant W as Worker (fetch stage)
  participant Y as yt-dlp
  participant G as googlevideo.com
  alt upload
    U->>A: POST /api/jobs/upload (multipart)
    A->>A: size cap → sniff → ffprobe → limits
    A->>B: put uploads/{video_id}/source.ext
    A->>DB: insert video + job (one tx)
  else YouTube link
    U->>A: POST /api/jobs/url
    A->>A: canonicalize_youtube_url (no network)
    A->>DB: insert video(source_url) + job
  end
  A-->>U: 202 {job_id}
  Note over W: later (T-062 drives this)
  W->>Y: metadata only (arg list, -- URL)
  Y-->>W: duration, live?, media URL, headers
  W->>W: reject live / > 60 s before any bytes
  loop ≤ 5 hops
    W->>W: https + allowed host + all DNS answers public
    W->>G: GET (no auto-redirect, byte cap)
  end
  W->>W: same sniff + ffprobe + limits as upload
  W->>B: put uploads/{video_id}/source.ext
  W->>DB: set_media_for_worker
```

## Key decisions (and why)
| ID | Decision | Why | Alternative rejected |
|---|---|---|---|
| D-017 | `BlobStore` protocol; local + S3 (boto3), presign ≤ 300 s; production requires S3 | Web and worker share no disk in prod; short links limit leakage | Serving files from a shared volume |
| D-018 | Upload checks cheapest first; blob stored before the job row, removed if the insert fails | Bad files never cost a parse or a DB row; the worker never sees a job without its file | Trusting extension / Content-Type |
| D-019 | Exact YouTube host allowlist + canonical rebuild; no network in the request | Only a URL we built ever reaches yt-dlp; 202 in ~8 ms | Regex "contains youtube.com"; fetching in the request |
| D-020 | yt-dlp metadata only; SSRF-guarded own download; optional cookies/proxy by env | Every hop and IP checked by us; YouTube blocking fails cleanly with `YOUTUBE_BLOCKED` | Letting yt-dlp download (no per-hop IP control) |

## How to demo / verify
```bash
cd backend
export TEST_DATABASE_URL=postgresql+psycopg://app:app@localhost:5432/app_test
pytest -q -k "blob or upload or url_rules or url_submit or net_rules or fetch or ytdlp"
python scripts/fetch_check.py   # real YouTube URL, owner's machine (set URL at the top)
```
Live: `POST /api/jobs/upload` with a valid clip → 202; a renamed text file → 415 `UNSUPPORTED_FORMAT`; a missing `X-Requested-With` header → 403; `POST /api/jobs/url` with `https://youtube.com.evil.io/watch?v=…` → 422 `URL_NOT_ALLOWED`.

## Tests added
- `test_blob_*` (41): key table (`..`, absolute, backslash, `%2e`, NUL), local round trip/range/symlink escape, S3 via moto incl. presign expiry.
- `test_upload*` (31): ffmpeg-generated fixtures, valid 202, fake 415, corrupt/truncated 422, 61 s 422, oversize 413 (header and chunked), nothing left in temp dir/blobs/DB after a rejection.
- `test_url_rules` / `test_url_submit` (72): accepted forms and SSRF tricks; endpoint 202 median < 100 ms.
- `test_net_rules`, `test_fetch_*`, `test_ytdlp_classifier` (103): IP table incl. mapped/6to4/Teredo, redirect to 169.254.169.254 blocked before contact, 5-hop limit, byte cap, yt-dlp argv, cookie file 0600 and always deleted, classifier on real stderr.
- Every security guard was mutation-checked (removed once, a test went red).

## AI corrections during this stage
- The first S3 test client lacked SigV4, so the presign TTL assertion failed, tests now build the client through the production `make_s3_client`.
- An assertion that the upload stream was cut off early could never hold (`TestClient` buffers the body), moved to ASGI-level unit tests.
- The size cap would have been turned into a 400 by FastAPI's form-parse handling, the middleware now sends 413 itself.
- `python-multipart` was never in requirements (only present locally), pinned.
- A classifier test expected a private video to be `YOUTUBE_BLOCKED`; it is `DOWNLOAD_FAILED`.
- An IPv6-unwrapping mutation survived because Python's `ipaddress` already blocks those ranges, added a direct `unwrap_ipv4` test.

## Known gaps / tech debt
- Real-URL fetch check (`scripts/fetch_check.py`) still to be run on the owner's machine; this session cannot reach YouTube.
- F-005: YouTube behaviour from the production IP unknown until deploy; cookies/proxy mitigation chosen then.
- F-006: `/jobs/...` aliases and validation errors in the `{error:{code,message}}` envelope.
- DNS rebinding between our lookup and connect remains (allowed domains are Google-controlled); full fix is connecting to the vetted IP with SNI pinning.

## Interview prep - questions you may get about this stage
1. Q: How do you know an upload is really a video?
   A: The extension and Content-Type are ignored. `core/file_sniff.py` checks magic bytes (ISO-BMFF `ftyp`, EBML, `RIFF…AVI`), then `ffprobe` must find a decodable video stream within the duration and size limits (`core/video_rules.py`).
2. Q: How do you stop a 10 GB upload?
   A: `BodySizeLimitMiddleware` rejects a too-large `Content-Length` before the app runs and counts the bytes actually received for chunked bodies, answering 413 once past the cap; the copy into the temp dir has its own cap too.
3. Q: How does the URL path prevent SSRF?
   A: Two layers. At submit, only `https` on four exact YouTube hosts is accepted and the URL is rebuilt from the video id. In the worker, the download never follows redirects automatically: each hop must be https on a Google video host, port 443, no userinfo, and **every** DNS answer must be public (IPv4-mapped/6to4/Teredo unwrapped) before any request is sent.
4. Q: What if YouTube blocks your server?
   A: yt-dlp's stderr is classified: bot checks, 403/429 and age gates become `YOUTUBE_BLOCKED` with "upload the file instead"; optional cookies or a proxy can be set by env var without code changes (D-020).
5. Q: Why store the blob before the database row?
   A: So the worker can never claim a job whose file is missing. If the insert fails, the blob is deleted; a crash between the two leaves at worst an orphan file, never a broken job.
