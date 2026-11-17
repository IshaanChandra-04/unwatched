# unwatched 0.2: what is on screen, and running for strangers

Date: 2026-11-17. Status: approved for build by the owner's request of the same day ("rerun
with screen capture and glean as much information as possible"; "refine this so it works for
others via GitHub"; "it should reliably run for as many users as possible"). Design calls below
are the builder's and are marked as such.

## Intent

Reels put much of their information on screen: numbered lists, repository names, the name of
the site being demonstrated, code in a terminal. Image posts and carousels carry everything in
the picture. Until now the pipeline read only captions and speech, so the master document says
"names are in the image" or "the site is never named" for dozens of posts. Capture what is on
screen and hand it to the digest, so those posts become knowledge instead of placeholders.

Second, the tool is public but was only ever run on the owner's Windows machine. Make it
installable and dependable for a stranger on Windows, macOS or Linux, with the first run
diagnosing its own setup.

## Goals

- Every fetched video post gets a small set of representative frames; every image post and
  carousel gets its full-size pictures. Both are turned into text ("on screen") that the digest
  input carries beside the caption and transcript.
- A post is re-presented to the digest when it gains material the digest has not seen, so
  frames added to old posts flow into the master document without a manual step.
- A digest handles a backlog in batches instead of one giant run.
- `unwatched login` installs the browser it needs; `unwatched doctor` explains what is missing;
  `unwatched schedule` works on macOS and Linux; CI runs on all three; releases can publish to
  PyPI.

## Non-goals

- Offline OCR. Text on reels is stylised and the point is understanding what is shown, not only
  the letters; headless Claude already is the tool's judgement engine. An OCR engine for users
  without Claude is a later option, not v1.
- Reading comments or the creator's bio link. Out of scope.
- Changing how transcription works. Audio stays as it is.

## Anti-goals

- Hammering Instagram: one extra download per video (the video-only stream, typically under
  2 MB at 720p) and one metadata call per image post, at the existing delay.
- A digest run so large it fails: the batch cap exists for that.
- Hidden cost: describing frames spends Claude turns per post; the config switch and the README
  say so, and the stage is skipped without Claude.

## Constraints

- No ffmpeg binary: PyAV (already a dependency through faster-whisper) decodes video and
  Instagram's VP9 streams; Pillow is added for resizing and JPEG writing.
- yt-dlp offers no image download for Instagram image posts, but its `thumbnails` list carries
  the full-size picture (up to 1440x1920 as checked on 2026-11-17), one per carousel entry.
- Headless Claude must run inside a folder holding nothing but the frames, with no MCP servers,
  the same way the digest is boxed.
- Windows sandboxed shells cannot open the headful browser; that is unchanged.

## Approaches considered

Getting what is on screen:

1. **Headless Claude reads sampled frames per post (chosen).** One dependency the tool already
   has; reads lists, code, UI and names tools; the output is prose the digest can use directly.
   Costs one short headless run per post.
2. Offline OCR (RapidOCR or Tesseract). No Claude needed, but a new heavy dependency or system
   binary, letters only, weak on stylised captions. Kept as a possible later engine.
3. Let the digest Claude open the frames itself. Hundreds of images in one run; rejected.

Getting the frames:

1. **Download the video-only DASH stream beside the existing audio and sample frames with PyAV
   (chosen).** Smallest change, smallest bytes; the audio path is untouched. Image posts and
   carousels come from yt-dlp's thumbnails at full size.
2. Download the progressive mp4 and transcribe from it. Changes the transcribe path and doubles
   the download. Rejected.
3. Screenshot the post page with Playwright. Needs the headful browser, slow, fragile. Rejected.

Knowing what the digest has seen:

1. **Record, per post, which materials the digest saw (chosen):** `state.json` gains
   `digested: {code: ["caption", "transcript", "frames"]}`. A post is due when it is absent or
   has a material not in its list. This also makes a batch cap possible and replaces the
   first-seen trick that `ingest --seen` used.
2. Keep the timestamp (`first_seen > last_digest`) and add file-time checks. Cannot support
   batches: posts left out of one batch would be lost to the next. Rejected.

## Design

### Stages

`fetch` (changed). For a video post, after the audio: `video/<code>.mp4` with
`-f "bestvideo[height<=720]/bestvideo/best[height<=720]/best"`. For an image post or carousel:
`--write-thumbnail --skip-download --ignore-no-formats-error` into `frames/<code>/`, so the
pictures land where the frames of a video would. A download is skipped when its file already
exists, so topping up old posts costs only the missing piece. `pending()` also returns a post
whose media is missing for its type (a video without `video/`, an image without `frames/`), so
posts fetched before 0.2 are completed by the next run.

`frames` (new, `frames.py`). For each `video/<code>.*` without `frames/<code>/`: decode, take a
candidate frame about every `duration / 40` seconds (at least every half second), keep a
candidate when its 16x28 grey thumbnail differs from the last kept one by more than 12 of 255
on average, always keep the first, cap at 12 by dropping the least different, save as JPEG
(quality 80, at most 720 px wide) named `01.jpg`, `02.jpg`, ... Builder's call: the thresholds
are constants with a `shortcut:` comment, not config.

`describe` (new, `describe.py`). For each `frames/<code>/` that holds images and has no
`frames/<code>.md`: run `claude -p --restricted --strict-mcp-config --allowedTools Read,Glob
--max-turns 30` with the frames folder as the working directory and a fixed prompt on stdin:
list every piece of visible text verbatim (titles, list items, code, commands, URLs, handles,
product and repository names, prices), say in one line per distinct scene what is shown, and
name the tools, sites, repositories and people that appear; quote, do not summarise or advise.
Stdout becomes `frames/<code>.md` when the exit code is 0 and the output is not empty.
Failures count in `meta/<code>.json` as `describe_retries`; after three the post is left alone.
A missing `claude` is reported the way the digest reports it.

`build` (changed). After the transcript block, an `On screen:` block quoting
`frames/<code>.md`. An image post with frames no longer says "no transcript" as if it had
nothing.

`digest` (changed). Due posts come from the digested record, oldest first, at most
`digest_max_posts` (config, default 40) per run; the input holds only those. On success each
presented post's current material list is recorded. When posts remain, the summary says how
many and that running `unwatched digest` again continues; that is not an error.

`run`. ingest → fetch → frames → transcribe → describe → build → digest. `frames` and
`describe` run when `frames = true` (config, default true); `describe` additionally needs the
digest's `claude`. A describe failure is reported in the summary and does not stop the chain.

### State migration

A `state.json` without `digested` is migrated once: every post whose `first_seen` is not after
`last_digest` is recorded with its current materials. `ingest --seen` records the materials of
the seeded posts directly instead of back-dating `first_seen`. `posts.new_since` goes away.

### Running for strangers

- `browser._context`: when Chromium's executable is missing, run
  `python -m playwright install chromium` once and retry, so the README's install is two lines:
  `uv tool install ...` and `unwatched login`.
- `unwatched doctor [--config FILE]`: checks Python version, yt-dlp, faster-whisper, PyAV,
  Pillow, the Playwright browser, the `claude` command (when the config enables the digest),
  the sign-in (cookies present and the browser profile holds a session), and the config's
  paths; prints one line per check with the fix; exit 1 when anything needs fixing.
- `schedule install|remove|status` on macOS writes a launchd agent
  (`~/Library/LaunchAgents/com.unwatched.daily.plist`, `StartCalendarInterval`, which runs a
  missed job at wake) and on Linux a crontab line tagged `# unwatched daily`. Status reports
  whether the job is installed and where.
- CI matrix adds `macos-latest` (browser tests stay Linux-only).
- A release workflow on tags `v*` builds with uv and publishes to PyPI through trusted
  publishing; `unwatched` is free on PyPI (checked 2026-11-17). The owner must register the
  trusted publisher on PyPI once; until then the publish step fails and the GitHub release is
  still made by hand as before.
- README: two-line install, `doctor`, the on-screen stage and its cost, scheduling on all three
  systems, a troubleshooting table. SKILL.md: the `On screen:` block is third-party data like
  the rest; image posts no longer need the browser.

## What is left to the builder

Exact prompt wording for `describe`; the doctor's check order and wording; launchd plist
details; test fixtures (a generated three-scene video, a fake `claude` that writes a
description); the CHANGELOG entries; the 0.2.0 release.
