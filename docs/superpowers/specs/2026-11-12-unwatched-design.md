# unwatched: design

Revision 2, 2026-11-14. Status: awaiting approval. Working name `unwatched` stands until the owner renames it.

**What changed in revision 2.** The owner wants the tool to run on its own once a day at 3 pm against the live inbox, so live collection from the alt account's DM thread and saved posts moves from "v2" into v1, and the data export becomes the bulk backfill path. A scheduler, an optional automatic Claude digest step, and an engineering-practice section (tests, CI, releases) were added. Actionable items from the owner's reel knowledge base are folded in and listed in the appendix.

## Intent

People save, like, or DM themselves reels they mean to come back to and never do. `unwatched` turns that backlog into a document they will actually read: every post listed, every video transcribed, and the ones that match the person's interests distilled into notes. It keeps doing so every day without being asked.

It generalises a one-off pipeline built in November 2026 for one DM thread (tech reels sent to an alt account, distilled into a master document with a link index, notes, and 34 transcripts) into something anyone can install, for any interest: tech, cooking, fashion, design systems, anything.

Why it exists:

1. The owner's own use: keep feeding Claude a growing knowledge base from tech and design reels to make Claude work better for them.
2. Public release on GitHub, built with the engineering practice the owner wants to show (tests, CI, releases), so other people can do the same for their own interests.

## Goals

- Collect from the places people stash reels on Instagram: a DM thread (the alt-account self-chat), saved posts and collections, and, through the export, likes and own archived posts.
- Run unattended once a day on the owner's Windows machine, incrementally: only posts not seen before are fetched and transcribed.
- No credentials in the tool. The user signs in once, in a browser window the tool opens, and the tool never sees, asks for, or stores the password.
- Transcribe locally on CPU. No API key is needed for the heavy part.
- Interest-agnostic. What to keep and what to extract lives in a short prose profile.
- Two audiences. Anyone with Python runs the CLI and gets captions plus transcripts. Claude Code users additionally get filtering and distillation through a bundled skill, on demand or as the daily job's last step.
- Observable. Every run leaves a one-line summary and a log, and exits non-zero with a plain reason when it needs a human (sign-in expired, cap exceeded).

## Non-goals for v1

- Live collection of likes and own archived posts. Those come from the export only.
- Carousel slide images and OCR. v1 keeps the caption for image posts; Claude can open the slides when the profile needs them. Upgrade path: gallery-dl.
- Any model API call inside the CLI. The optional digest step shells out to the user's own Claude Code install; nothing else talks to a model.
- Desktop notifications. v1 reports through the log and exit code; a Windows toast is a v1.1 item.
- Any write action on Instagram. A GUI. Other platforms, though the post record is platform-neutral.

## Anti-goals

- Anything that asks for, stores, or automates entry of Instagram credentials.
- Bulk-hammering Instagram. The daily sweep stops as soon as it reaches posts it already knows. Fetch is sequential, delayed, and capped, and the cap must be raised on purpose.
- A tool that only works inside Claude.
- A tool that silently papers over failures. A failed step is logged and surfaced, never patched around.

## Constraints

- Dev machine: Windows 11, Python 3.12, 8 CPUs, no GPU. Installed: uv 0.13, git 2.55, Claude Code CLI 2.1.322, Windows Task Scheduler. Not installed: Firefox, yt-dlp, Playwright.
- A headful browser needs an interactive Windows session, so the scheduled task runs only while the user is signed in (a locked screen is fine). Headless Chromium is more likely to trip Instagram's automation checks and is not used.
- Instagram sessions expire and Instagram sometimes forces a re-verification. The tool detects the login page, stops, and asks the user to run `unwatched login` again.
- Instagram's terms forbid automated collection. The sweep reads only the user's own thread and saved page, incrementally, and the fetch step opens one post at a time with a delay. Account risk is the user's, and the README says so.
- faster-whisper needs `av<14` on Python 3.12. Measured as processing time divided by audio length on this CPU: large-v3-turbo about 2.0, small about 0.4.
- yt-dlp needs cookies for most Instagram posts. The tool exports them from its own Playwright profile, so the user never handles a cookies file.
- The export (Instagram's "Download your information", JSON) takes hours to two days and its field names are known from memory and third-party parsers, not Meta documentation. Export ingest is validated against a real export before release.
- Licence MIT. Repo at `C:\Users\<you>\Documents\Claude Plugin Repos\unwatched`.

## Approaches considered

### Form (decided by the owner: CLI plus a thin Claude skill)

1. **Claude plugin only.** Fastest, but only Claude Code users could run it, and Claude would drive the browser every day, which is slow, token-hungry, and non-deterministic. Rejected.
2. **Standalone app with its own model API step.** Duplicates Claude and makes classification ours to maintain. Rejected.
3. **CLI plus skill.** The CLI does all deterministic work; the skill (or a headless Claude run) does the judgement. Chosen. This is also the "give it a runtime, not a loop" principle from the knowledge base: scripts collect, the model reads only the final output.

### Collection source (my call, revised: live first, export for backfill)

1. **Live, through Playwright on a persistent profile the user signs into once.** Fresh every day, covers exactly the DM thread and saved page, and the same session supplies cookies for downloads. Costs: a 150 MB Chromium download, Instagram's DOM can change, and the account risk above. Chosen for the daily job.
2. **The data export.** No scraping and it covers likes and archive, but it arrives days later and must be requested by hand, so it cannot drive a daily job. Kept as the backfill and the only source for likes and archived posts.
3. **A plain links file.** Any text with Instagram URLs. Kept; it is how the prototype's link list feeds in.
4. **Instagram Graph API.** Cannot read saved posts or DMs. Not viable.

### Scheduler (my call: Windows Task Scheduler)

1. **Windows Task Scheduler**, registered by the tool itself. Native, no extra process, supports "run when missed" and "wake to run". Chosen.
2. **A Claude scheduled task or cloud routine.** Cloud routines cannot reach the local browser session. Desktop scheduled tasks need the app open and spend tokens on collection that a script does for free. Rejected for collection; Claude is only used for the digest.
3. **An always-on server or Raspberry Pi.** Would remove the "computer must be on" problem, but signing into Instagram from a datacenter IP invites checkpoints, and it is more to run. Not for v1; a Pi at home is the natural v2 if the laptop proves unreliable.

### Daily digest (my call: optional headless Claude step, on by default for the owner)

1. **`claude -p` as the last step of the job**, with the skill's instructions, the new posts, the profile, and the master document path. The report updates itself every day. Costs one Claude Code run a day from the user's plan. Chosen, behind a `--digest` flag so the CLI alone needs no Claude.
2. **On demand only**, the user runs the skill when they want. Still available; it is the same skill.

### Download and transcription (unchanged)

yt-dlp for metadata and audio-only download. faster-whisper, CPU int8, VAD filter, beam size 5, default model small, turbo re-run on kept posts.

## The design

### Repo layout

```
unwatched/
  pyproject.toml                  package "unwatched", console script "unwatched", uv-managed, uv.lock committed
  src/unwatched/
    cli.py                        argparse: login | ingest | fetch | transcribe | build | digest | run | schedule | status
    browser.py                    Playwright persistent profile: login check, DM thread sweep, saved grid sweep, cookie export
    shortcode.py                  media id <-> shortcode, URL regex
    ingest.py                     export zip or folder, links files, and live sweeps -> posts.jsonl
    fetch.py                      yt-dlp metadata and audio per post, with the cap and delay
    transcribe.py                 faster-whisper -> transcripts/<code>.txt
    build.py                      posts + meta + transcripts -> digest-input.md
    digest.py                     runs `claude -p` with the skill prompt, checks the result
    schedule.py                   registers, removes, and reports the Task Scheduler job
    state.py                      work/state.json: last run, last digest, last error
  skills/unwatched/SKILL.md       the Claude skill (used on demand and by digest.py)
  .claude-plugin/plugin.json      plus marketplace.json
  profiles/tech.md  design.md  cooking.md  fashion.md
  tests/                          pytest; fixtures for export JSON and a static DM-thread HTML page
  .github/workflows/ci.yml        ruff + pytest on windows-latest and ubuntu-latest
  .pre-commit-config.yaml  README.md  CONTRIBUTING.md  SECURITY.md  CHANGELOG.md  LICENSE
  docs/superpowers/specs/  docs/superpowers/plans/
```

Dependencies: playwright, yt-dlp, faster-whisper, `av<14`. Dev: ruff, pytest, pre-commit. Standard library for everything else. No click, rich, or pydantic.

### Data contract: `work/posts.jsonl`

One line per unique shortcode:

```json
{"code": "DbnopHDNWSw",
 "url": "https://www.instagram.com/p/DbnopHDNWSw/",
 "sources": [
   {"kind": "dm", "name": "kungfookah", "via": "live", "ts": "2026-11-13T21:40:02Z"},
   {"kind": "saved", "name": "Tech", "via": "export", "ts": "2026-10-31T09:10:00Z", "text": "share caption if present"}
 ],
 "first_seen": "2026-10-31T09:10:00Z",
 "local_media": null}
```

`kind` is one of `saved`, `liked`, `archived`, `dm`, `links`; `via` is `live`, `export`, or `file`. Shortcodes come from URLs (`instagram.com/(p|reel|reels|tv)/<code>`) or, on the DM page where cards carry no link, from the thumbnail's `ig_cache_key`, a base64 media id converted with Instagram's 64-character alphabet. `local_media` is set only for archived posts, whose files ship inside the export.

After fetch: `work/meta/<code>.json` (uploader, caption, upload date, duration, media type, error) and `work/audio/<code>.m4a` for videos. After transcribe: `work/transcripts/<code>.txt`. `work/state.json` holds last run time, last digest time, and the last error.

### Commands

- `unwatched login`
  Opens the tool's own Chromium window on instagram.com. The user signs in (and completes any two-factor step) themselves. The tool waits for the session cookie, confirms, and closes. Nothing is typed by the tool. The profile lives under the user's home directory with user-only permissions.
- `unwatched ingest [EXPORT] [--links FILE]... [--dm THREAD_URL]... [--saved] --work work/`
  Export and links as before. `--dm` sweeps a thread newest-first: scroll in small steps, decode each card, stop after 20 consecutive already-known codes or at the thread's start (the profile card). `--full` disables the early stop. `--saved` sweeps the saved grid and each collection the same way; grid tiles carry real links. If the login page appears, exit with code 3 and the message "sign-in expired, run `unwatched login`". Prints counts per source and per thread.
- `unwatched fetch --work work/ [--kinds saved,archived,dm] [--thread NAME]... [--since DATE] [--max 300] [--delay 3] [--only CODE...]`
  Selection by kind (likes opt-in), thread, and date. Stops if the selection exceeds `--max` unless raised. Cookies come from the Playwright profile automatically; `--cookies FILE` overrides. Sequential yt-dlp metadata, then audio-only for videos. Errors are recorded per post and never abort the run.
- `unwatched transcribe --work work/ [--model small|large-v3-turbo] [--language en] [--only CODE...]`
  Default small. `--only` lets the skill re-run kept posts with turbo.
- `unwatched build --work work/ --out digest-input.md [--new-only]`
  Index table plus one section per post. `--new-only` emits only posts first seen since the last digest, for the daily step.
- `unwatched digest --work work/ --profile PROFILE --master MASTER.md`
  Builds the new-only input, runs `claude -p` with the skill's instructions, the profile, and the master path, allowing only file reads and edits under the work and master locations, with a turn limit. Succeeds only if the master file changed and Claude's final message carries the completion marker the skill prints; otherwise exit non-zero with the captured output in the log. Updates `last_digest`.
- `unwatched run --config unwatched.toml`
  ingest (live sources from the config) -> fetch -> transcribe -> build -> digest if enabled. Writes `work/logs/YYYY-MM-DD.log` and a one-line summary to `state.json`. Below-normal process priority so a 3 pm run does not fight the user's work.
- `unwatched schedule install [--at 15:00] | remove | status`
  Registers a daily Task Scheduler job that runs `unwatched run` with: run only when the user is logged on, start as soon as possible if the start was missed, wake the computer to run, allowed on battery, two-hour time limit, lowest priority. `status` shows the next and last run and the last result.
- `unwatched status` prints the last run summary and any pending human action.

### Configuration: `unwatched.toml`

```toml
work = "C:/Users/me/unwatched-work"
profile = "profiles/tech.md"
master = "C:/Users/me/Documents/reels/master.md"
digest = true

[sources]
dm = ["https://www.instagram.com/direct/t/<thread-id>/"]
saved = true

[fetch]
kinds = ["saved", "dm"]
max = 300
delay = 3
```

### Interest profile

A short markdown file in prose: what to keep, what to skip, what to extract, and the shape of the output. Example `profiles/design.md`, the owner's next use:

```
# Design systems

Keep: UI and web design rules, design systems, typography and colour guidance, component libraries, design tools and skills, prompts that improve visual output.
Skip: generic "AI slop" complaints with no concrete rule, marketing for paid courses.
Extract per post: each concrete rule or recommendation, the tool or library named, the source's reasoning, and any prompt or checklist worth reusing verbatim.
Output: a rule book grouped by topic (layout, type, colour, motion, components, process), a tools list, then the transcripts of kept posts.
```

No schema and no parser. Claude reads it.

### The Claude skill (`skills/unwatched/SKILL.md`)

Used two ways: on demand in a Claude Code session, and headless by `digest.py`. It teaches Claude to:

1. Check `unwatched` is installed and signed in (`unwatched status`); say how if not.
2. Locate or ask for the profile and the master document. Offer the bundled profiles.
3. On demand: run `ingest`, show the counts, confirm what to fetch, then run `fetch`, `transcribe`, and `build` in the background and wait for the process to finish rather than polling in a loop.
4. Read the digest input once. Apply the profile: keep or skip each post. Correct misheard names only where the intended name is clear. Merge repeated points.
5. Update the master document in place: Part 1 distilled notes by the profile's extract rules (merge, do not duplicate), Part 2 cleaned transcripts of kept posts (append), Part 3 the full link index with kept or skipped flags (append). Keep a dated "Last updated" line and a changelog of what each run added.
6. Offer a turbo re-run on kept posts when quality matters.
7. End with one line: kept versus total this run, and print the completion marker.

Rules baked in: never sign in or type credentials; never guess a name correction; never raise the fetch cap without the user; never poll in a loop; always state kept versus total.

### Scheduling and its limits

The daily job is a Windows Task Scheduler task at 15:00 local time. What can hold it up, and what the design does about each:

- **The computer is off.** Nothing runs. With "start when missed" the job runs at the next sign-in. The sweep then catches up on every day it missed because it only stops at posts it already knows.
- **The computer is asleep.** "Wake to run" wakes it if the power plan allows wake timers (laptops on battery often do not). Hibernation and shutdown are not wakeable.
- **Nobody is signed in.** The browser is headful, so the task is registered to run only when the user is logged on. A locked screen is fine.
- **Instagram asks for a fresh sign-in.** The job exits with code 3, `status` says "run `unwatched login`", and the next run resumes where it stopped.
- **Fetch cap exceeded** after a long gap. The job stops before fetching and says how many were selected. The user reruns with `--max` raised.
- **Windows Update reboot, VPN drop, low battery.** The run fails or is skipped; the next one catches up. Nothing is lost because collection is idempotent.
- **Cost.** The digest step spends one Claude Code run a day from the user's plan; `digest = false` turns it off.

### Engineering practice

The repo is also a demonstration of working properly, so:

- **Version control from the first commit.** Small commits in Conventional Commits form. Feature branches and pull requests even solo, so CI runs before merge.
- **Reproducible environment.** uv project, `uv.lock` committed, `requires-python >= 3.11`, every command run through `uv run`.
- **Tests first** (superpowers test-driven development) for the pure parts: shortcode decode, export parsing, links regex, fetch selection and cap, build rendering, sweep stop logic against a static HTML fixture, and config loading. Network and model steps are integration-tested by a documented smoke run, not in CI.
- **Lint and format** with ruff, enforced by pre-commit and CI.
- **CI** on GitHub Actions for every push and pull request: ruff check, ruff format check, pytest on windows-latest and ubuntu-latest with Python 3.12. No network in CI.
- **Releases.** Semantic version tags, GitHub Releases with notes, CHANGELOG in Keep a Changelog form. Dependabot for dependency updates. PyPI later.
- **Security.** Cookies and the browser profile never enter logs or the repo (gitignored, user-only permissions). SECURITY.md says how to report. Cloudflare's security-audit-skill is run on the repo before the first public release and before each release after that, more than once, since a single run finds about half of what repeated runs find.
- **Docs.** README (what, install, the five-minute setup, the daily job, the Instagram terms note, privacy), CONTRIBUTING, this spec and the implementation plan under `docs/superpowers/`.
- **Observability.** Dated logs, a one-line run summary, non-zero exit codes with reasons, `unwatched status`.

### Release

- MIT licence. README as above, plus the "request the export" steps for backfill and the plugin install line for Claude Code users.
- `uv tool install git+https://github.com/<user>/unwatched`, then `unwatched login`, `unwatched schedule install`.
- Before the first public push: validate export ingest against a real export, replace the synthetic fixture with a redacted real structure, run the security audit, and run the `open-source-launch` checklist.

### Known pitfalls to carry into code and README

- The `av<14` pin. First-run downloads: Chromium about 150 MB, the small model about 500 MB, turbo 1.6 GB.
- The DM list is a column-reverse, virtualised scroller: scroll in about 450-pixel steps with a pause, and re-find the largest scroller each step. Fast jumps skip cards.
- Carousel child codes redirect to the parent; deduplicate again after fetch using yt-dlp's id.
- Export JSON stores UTF-8 as Latin-1; decode with a latin-1 to utf-8 round trip and fall back on failure.
- Playwright's Chromium can trip Instagram's automation checks. Keep it headful, keep the persistent profile, add no automation-hiding tricks; if Instagram checkpoints the account, stop and tell the user.
- `claude -p` output must be checked for the completion marker and the changed file, not just the exit code.

### Left to the builder

- argparse wiring, log format, file naming inside `work/`.
- yt-dlp options, subprocess versus library use, image-only detection, and cookie export format from the Playwright profile.
- Exact Task Scheduler registration (PowerShell `Register-ScheduledTask` with the settings above).
- The static HTML fixture for the sweep test, the `claude -p` flags (allowed tools, turn limit), and the completion marker text.
- `marketplace.json` fields.

## Open for the owner

1. Name: `unwatched` unless told otherwise. A later rename is mechanical but touches every file, so decide before the first push.
2. GitHub handle, and a `gh auth login` in a terminal when it is time to push.
3. Confirm the schedule: 15:00 local, daily, run when missed, wake from sleep.
4. Keep the daily Claude digest on (one Claude Code run a day from your plan), or run it on demand only.
5. Sign into Instagram once in the tool's browser window during the build, for the live sweep test.
6. Optional: still request the data export from the alt account for likes and archive backfill.

## Appendix: what the reel knowledge base contributes

Adopted in this design:

- Scripts collect, the model reads the final output (rollins.io, Anthropic's code-execution-with-MCP). The CLI does everything deterministic; Claude sees one file.
- Tests at every level and a CI pipeline before anything else (rollins.io "vibe coders to software engineer"). Engineering practice section.
- No polling loops, no fallbacks that patch around failures (ayoships). Skill rules and the anti-goal.
- A daily job with pass or fail logged per run, and tests that prove yesterday's work still runs (raycfu's loop.sh pattern, simplified). `state.json`, dated logs, CI.
- Security audit before launch, repeated (Cloudflare security-audit-skill).
- Pick one tool per need, do not install all thirty (okaashish). Already in use here: Superpowers, Ponytail, Headroom, Impeccable, UI UX Pro Max, Humanizer, I Have ADHD, REA. Nothing more is installed for this project.
- Playwright as the browser driver (petergriffin.ai's Playwright CLI item, generalised).
- Design-system extraction as the next profile (TasteSkill, AwesomeDesign, Web Design Guidelines, filatov.design, naman_labs posts are the first inputs for `profiles/design.md`).

Noted for later, not in v1:

- Karakeep (self-hosted bookmarks with AI tagging) as prior art and a possible export target.
- claude-mem or gstack if sessions on this repo start losing context.
- Promptfoo if the digest prompt ever needs evaluation against a fixed set of posts.
- claude-video or Gemini for reels whose knowledge is on-screen rather than spoken.

Not applicable: open-source SaaS alternatives, self-hosting stack, AI agency lessons, free model APIs.
