# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
