# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-11-17

### Added

- `pictures`: the slides and the caption of image posts and carousels, fetched through the signed-in browser (yt-dlp exposes only the cover picture and no caption for them).
- `frames`: the frames of each video that show something new, sampled with PyAV (twelve at most, 720 px wide), plus the video-only stream in `fetch` that feeds them.
- `describe`: headless Claude Code reads a post's pictures and writes what is on screen (text verbatim, scenes, names) to `frames/<code>.md`; `build` carries it into the digest input as an `On screen:` block.
- The digest records which materials it saw per post (`state.json["digested"]`), re-presents a post that gained a transcript or on-screen text, and works in batches of `digest_max_posts` (default 40); the summary says how many posts are waiting.
- `doctor`: checks Python, the dependencies, the browser, the sign-in and the config, and says what to fix.
- `schedule` on macOS (launchd agent) and Linux (crontab line with the full path and `DISPLAY=:0`); `status` and `remove` no longer call PowerShell off Windows.
- `unwatched login` installs Chromium itself the first time, so the install is two commands.
- The four bundled profiles ship in the wheel; `profile = "tech"` names one.
- Config keys `frames` and `digest_max_posts`; unknown keys and wrong types are refused with the key named.
- CI on macOS and on Python 3.11 and 3.13; browser tests on every system; a release workflow that publishes tagged versions to PyPI through trusted publishing; a bug-report form and a code of conduct.

### Changed

- `fetch` skips downloads whose files exist and completes posts fetched before 0.2 (video stream, pictures) on the next run.
- `digest = true` without `profile` and `master` is reported in the summary instead of silently skipped.
- Hand-run commands print their progress; Ctrl-C exits 130; a bad config is printed, not raised.
- The saved-page username lookup reports a missing username as such instead of an expired session.
- `requires-python` is `>=3.11,<3.14` (PyAV 13 has no 3.14 wheels).

### Fixed

- `run` overwrote the state the digest had just saved with its pre-run copy, so `last_digest` never advanced through the daily job and the same posts were offered again the next day.
- One stalled yt-dlp download no longer holds the daily run: calls time out after 300 s and the post is recorded as failed. The `describe` run has the same guard (600 s), stops after three failures in a row, and a missing `claude` is reported once without counting against the posts.
- A re-fetch keeps what the browser and `describe` recorded for the post (slides, caption, attempts), and a failed re-fetch keeps the previous good record.

## [0.1.1] - 2026-11-17

### Added

- `claude` config key: the Claude Code executable the daily digest runs, for machines where the
  scheduled job's PATH does not include it.

### Fixed

- `run`: a live source that fails (a saved page that never finishes loading, say) no longer
  crashes the run and loses what the other sources found; the error goes to the log and
  `status`, and the chain continues with the posts it has.
- `digest`: a missing `claude` command is reported as `claude not found: <name>` with the config
  key to set, instead of a bare operating-system file error.
- `ingest --dm`: a thread URL without a trailing slash names the thread after its id, not `t`.
- `login`: a session cookie on Instagram's login or challenge page no longer counts as signed in,
  so a session Instagram invalidated does not loop through "run unwatched login".
- `fetch`: a post whose fetch keeps failing (deleted, private) is given up after three attempts
  instead of being hit every day; the attempts are counted as `retries` in its meta file.
- `fetch --kinds "saved, dm"`: spaces around the kind names are ignored.
- `ingest --seen` after a digest: the seeded posts no longer surface in the next digest.
- `build`: a post whose fetch failed shows `?` as its type in the index, not `None`.
- Config: `~` in `work`, `profile`, `master`, `sources.links` and `sources.export` is the home
  folder.

### Changed

- `build`: captions and transcripts are rendered as blockquotes, so headless Claude reads them as
  quoted data rather than as part of the prompt.
- `run`: the dated log holds only unwatched's lines; `huggingface_hub` and `faster_whisper` log at
  WARNING and above.
- `schedule install` checks that `--config` exists and parses before registering the task.

### Security

- `digest`: the headless `claude -p` run passes `--strict-mcp-config`, so the daily job loads none
  of the user's MCP servers.
- CI pins `actions/checkout` and `astral-sh/setup-uv` to commit SHAs; Dependabot keeps them
  current.

## [0.1.0] - 2026-11-14

### Added

- `unwatched login`: sign in once in the tool's own Chromium window; the tool types nothing.
- `unwatched ingest`: collect posts from Instagram's data export (saved, collections, likes,
  archived posts, every DM thread), from any text file of links, and live from a DM thread and
  the saved page, stopping at posts already known. `--seen` marks posts as already processed.
- `unwatched fetch`: yt-dlp metadata and audio-only download per post, selected by kind, thread
  and date, sequential with a delay and a cap that must be raised on purpose; failures are
  recorded per post and never abort the run.
- `unwatched transcribe`: local faster-whisper transcription, default model `small`, with
  `--only` for a turbo re-run of kept posts.
- `unwatched build`: one digest input file with every post's caption and transcript;
  `--new-only` for the daily step.
- `unwatched digest`: headless Claude Code run that updates the master document, verified by a
  completion marker and a changed file.
- `unwatched run`: the whole chain from a TOML config, with dated logs and a one-line summary.
- `unwatched schedule`: register, remove and inspect the daily Windows Task Scheduler job
  (run when missed, wake to run, only when logged on, low priority).
- Claude Code skill and plugin manifest; bundled interest profiles for tech, design systems,
  cooking and fashion.
- Project scaffold: uv-managed package, ruff, pytest, pre-commit, GitHub Actions CI on Windows
  and Linux, Dependabot, MIT licence, security policy.
