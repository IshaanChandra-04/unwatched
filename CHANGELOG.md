# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
