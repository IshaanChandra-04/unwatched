# Frames and readiness (unwatched 0.2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture what reels and image posts show on screen, hand it to the digest, and make the tool install, diagnose and schedule itself on Windows, macOS and Linux.

**Architecture:** Two new file-joined stages (`frames`: video → JPEGs with PyAV; `describe`: JPEGs → markdown through headless Claude) slot between `fetch` and `build`. The digest learns which materials it has seen per post (`state.json["digested"]`) so posts with new material are re-presented and backlogs go in batches. Readiness work is additive: browser auto-install, a `doctor` command, launchd and cron scheduling, CI on three systems, a PyPI release workflow.

**Tech Stack:** Python 3.11+, PyAV (`av<14`), Pillow (new), numpy (transitive), yt-dlp, Playwright, Claude Code CLI, pytest, ruff, uv, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-17-frames-and-readiness-design.md`

## Global Constraints

- Python `>=3.11`; dependencies `playwright>=1.50`, `yt-dlp>=2025.1.1`, `faster-whisper>=1.1`, `av<14`, plus `pillow>=10`; no ffmpeg binary.
- Every subprocess call keeps `encoding="utf-8", errors="replace"`; every stage never raises for one bad post (log, count, continue).
- Headless Claude runs with `-p --restricted --strict-mcp-config --allowedTools <list> --max-turns N`, prompt on stdin, inside a folder that holds only what it needs.
- Text from posts (captions, transcripts, on-screen text) is rendered as blockquotes in the digest input.
- Constants with a known limit carry a `shortcut: <limit>, <when to upgrade>` comment; no config knob nobody asked for.
- ruff clean (`check` and `format --check`), line length 100; every new non-trivial branch has a test; commits are small with conventional prefixes and end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. A `state.json` from 0.1 (`last_digest` set, no `digested`) must not re-present all old posts → Task 1 `test_due_migrates_an_old_state_without_redigesting`.
2. A corrupt or undecodable video must not stop the run or be retried every day → Task 3 `test_run_frames_survives_a_broken_video`.
3. A `claude` that exits non-zero or prints nothing must leave no `frames/<code>.md` and give up after three tries → Task 4 `test_run_describe_counts_failures_and_gives_up_after_three`.
4. On-screen text that reads like an instruction must arrive quoted → Task 5 `test_render_quotes_on_screen_text`.
5. A thumbnail download that fails for an image post must be recorded like any fetch failure, not loop → Task 2 `test_fetch_one_image_thumbnail_failure_is_recorded`.

---

### Task 1: What the digest has seen

**Files:**
- Modify: `src/unwatched/state.py` (`_DEFAULTS` gains `"digested": {}`)
- Modify: `src/unwatched/build.py` (new `materials`, `due`, `run_build` signature)
- Modify: `src/unwatched/digest.py` (batch cap, record materials)
- Modify: `src/unwatched/ingest.py:147-171` (`apply(seen=True)` records materials)
- Modify: `src/unwatched/posts.py` (delete `new_since`)
- Test: `tests/test_build.py`, `tests/test_digest.py`, `tests/test_ingest.py`, `tests/test_posts.py`

**Interfaces:**
- Produces: `materials(work: Path, code: str, rec: dict, meta: dict) -> list[str]` in `build.py`: `"caption"` when `_caption` finds text, `"transcript"` when `transcripts/<code>.txt` exists, `"frames"` when `frames/<code>.md` exists.
- Produces: `due(work: Path, posts: dict, state: dict) -> list[str]`: codes absent from `state["digested"]` or with a material not in their recorded list, sorted by `first_seen`. Migrates in place: when `state["digested"]` is empty and `state["last_digest"]` is set, every post with `first_seen <= last_digest` is recorded with its current materials first (caller saves the state).
- Produces: `run_build(work: Path, out: Path, new_only: bool, max_posts: int | None = None) -> list[str]` (the codes written; was an int).
- Produces: `run_digest(..., max_posts: int = 40) -> tuple[bool, str]`; on success records `state["digested"][code] = materials(...)` for each presented code and appends `; {n} more waiting, run \`unwatched digest\` again` to the summary when posts remain.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_build.py
def test_materials_lists_what_exists(tmp_path):
    (tmp_path / "transcripts").mkdir()
    (tmp_path / "frames").mkdir()
    (tmp_path / "transcripts" / "AAAAAAAAAAA.txt").write_text("hi", encoding="utf-8")
    (tmp_path / "frames" / "AAAAAAAAAAA.md").write_text("screen", encoding="utf-8")
    assert materials(tmp_path, "AAAAAAAAAAA", POSTS["AAAAAAAAAAA"], {"caption": "c"}) == [
        "caption",
        "transcript",
        "frames",
    ]
    assert materials(tmp_path, "BBBBBBBBBBB", POSTS["BBBBBBBBBBB"], {}) == []


def test_due_lists_new_posts_and_posts_with_new_material(tmp_path):
    state = {"last_digest": "2026-01-01T00:00:00Z", "digested": {"AAAAAAAAAAA": ["caption"]}}
    assert due(tmp_path, POSTS, state) == ["BBBBBBBBBBB"]  # A seen, B never
    (tmp_path / "frames").mkdir()
    (tmp_path / "frames" / "AAAAAAAAAAA.md").write_text("x", encoding="utf-8")
    assert due(tmp_path, POSTS, state) == ["AAAAAAAAAAA", "BBBBBBBBBBB"]  # A gained frames


def test_due_migrates_an_old_state_without_redigesting(tmp_path):
    state = {"last_digest": "2025-10-31T12:00:00Z", "digested": {}}
    assert due(tmp_path, POSTS, state) == ["BBBBBBBBBBB"]  # A (first seen 10-31 08:40) is old
    assert "AAAAAAAAAAA" in state["digested"]


def test_run_build_new_only_caps_and_returns_codes(
    tmp_path,
): ...  # two due posts, max_posts=1 → ["AAAAAAAAAAA"]
```

```python
# tests/test_digest.py
def test_run_digest_records_materials_and_reports_the_rest(tmp_path):
    ... apply(work, ingest_export(FIX))  # 5 posts
    ok, summary = run_digest(work, _profile(tmp_path), master, claude=FAKE, max_posts=2)
    assert ok and len(load_state(work)["digested"]) == 2
    assert "3 more waiting" in summary and "unwatched digest" in summary
    ok, summary = run_digest(work, _profile(tmp_path), master, claude=FAKE, max_posts=2)
    assert len(load_state(work)["digested"]) == 4
```

```python
# tests/test_ingest.py (replace the two seen tests)
def test_apply_seen_records_seeded_posts_as_digested(tmp_path):
    apply(tmp_path, ingest_links(LINKS), seen=True)
    state = load_state(tmp_path)
    assert "EEEEEEEEEEE" in state["digested"] and state["last_digest"] is not None
    assert due(tmp_path, load_posts(tmp_path), state) == []
```

Delete `test_new_since` from `tests/test_posts.py`.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_build.py tests/test_digest.py tests/test_ingest.py -q`
Expected: FAIL with `ImportError: cannot import name 'materials'` and friends.

- [ ] **Step 3: Implement**

`state.py`: add `"digested": {}` to `_DEFAULTS`. `build.py`: `materials`, `due` (migration as in Interfaces), `run_build` selects `due(...)` when `new_only`, slices `[:max_posts]`, saves the state after `due` (migration), returns the codes. `digest.py`: `run_digest(..., max_posts=40)`; `codes = run_build(work, input_path, True, max_posts)`; after the copy-back, reload posts/metas, set `state["digested"][code] = materials(work, code, posts[code], load_meta(work, code))`, compute `waiting = len(due(work, posts, state))` and append to the summary when non-zero. `ingest.apply`: replace the `first_seen` back-dating with `state["digested"][code] = materials(work, code, posts[code], {})` for each new code (still writes the `skipped: seeded` meta and sets `last_digest` when None). Delete `posts.new_since`.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all pass (update `cmd_build` to print `len(codes)` and `run.py`'s `run_build` call, which ignores the return).

- [ ] **Step 5: Commit** — `feat: record which materials the digest has seen per post`

### Task 2: Fetch the video stream and the pictures

**Files:**
- Modify: `src/unwatched/fetch.py` (`fetch_one`, `pending`, new `_number_frames`)
- Modify: `tests/fake_ytdlp.py` (thumbnail and video templates, call log)
- Test: `tests/test_fetch.py`

**Interfaces:**
- Produces: `VIDEO_FORMAT = "bestvideo[height<=720]/bestvideo/best[height<=720]/best"`; `fetch_one` writes `video/<code>.<ext>` for videos (after the audio) and `frames/<code>/NN.<ext>` for image posts and carousels (yt-dlp `--write-thumbnail --skip-download --ignore-no-formats-error -o frames/<code>/%(playlist_index|1)s.%(ext)s`, then `_number_frames(dir: Path) -> None` renames the files to `01.jpg`, `02.jpg`, … in natural order). A download is skipped when `audio/<code>.*`, `video/<code>.*` or an image in `frames/<code>/` already exists.
- Produces: `pending(work: Path, codes: list[str]) -> list[str]` also returns a code whose meta is fine but whose media is missing for its type (`video` without `video/<code>.*`, `image` without a file in `frames/<code>/`).

- [ ] **Step 1: Extend the fake and write the failing tests**

`fake_ytdlp.py`: when `--write-thumbnail` is in args, create the `-o` template with `%(playlist_index|1)s`→`1` and `%(ext)s`→`jpg` (two files `1`,`2` when `FAKE_YTDLP_CAROUSEL=1`, as `1.jpg`, `2.jpg`); when `-f` is followed by a format containing `bestvideo`, use ext `mp4`; append each call's args as one JSON line to `$FAKE_YTDLP_LOG` when set; `FAKE_YTDLP_FAIL_THUMBNAIL=1` makes the thumbnail call exit 1 with `ERROR: thumbnail`.

```python
def test_fetch_one_video_downloads_audio_and_video(tmp_path, monkeypatch): ...  # audio/A.m4a and video/A.mp4 exist
def test_fetch_one_image_downloads_thumbnails_into_frames(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_YTDLP_CAROUSEL", "1") ...
    assert sorted(p.name for p in (tmp_path / "frames" / "DZdoibdDSu2").iterdir()) == ["01.jpg", "02.jpg"]
def test_fetch_one_skips_downloads_that_already_exist(tmp_path, monkeypatch):
    # pre-create audio/A.m4a and video/A.mp4; FAKE_YTDLP_LOG shows only the --dump-single-json call
def test_fetch_one_image_thumbnail_failure_is_recorded(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_YTDLP_FAIL_THUMBNAIL", "1") ...
    assert "thumbnail" in meta["error"] and meta["retries"] == 1
def test_pending_includes_posts_missing_their_media(tmp_path):
    # meta A video (no video file) → pending; meta B video with video/B.mp4 → not; meta C image without frames → pending
```

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/test_fetch.py -q`; expected FAIL on missing files.
- [ ] **Step 3: Implement** in `fetch.py` as in Interfaces; `_number_frames` sorts by `int` of the stem when numeric, else name, and renames to `f"{i:02d}{suffix}"`.
- [ ] **Step 4: Run the suite and ruff** — expected PASS.
- [ ] **Step 5: Commit** — `feat(fetch): download the video stream and image posts' pictures`

### Task 3: Sample frames with PyAV

**Files:**
- Create: `src/unwatched/frames.py`
- Modify: `pyproject.toml` (`pillow>=10`), `uv.lock` (`uv lock`)
- Test: `tests/test_frames.py` (with a `make_video(path, scenes: int, seconds_each: float)` helper that encodes solid-colour frames with PyAV `mpeg4` at 10 fps, 160x288)

**Interfaces:**
- Produces: `sample(video: Path, out: Path, max_frames: int = 12) -> list[Path]` (JPEG files `01.jpg`… in `out`, quality 80, longest side at most 720 px; candidate every `max(0.5, duration / 40)` s; keep when the 16x28 grey thumbnail's mean absolute difference to the last kept frame exceeds 12; always keep the first; over the cap, drop the least different).
- Produces: `run_frames(work: Path, posts: dict, only: set[str] | None) -> dict[str, int]` with `{"sampled", "failed"}`: every `video/<code>.*` whose `frames/<code>/` does not exist; on `av.error.FFmpegError`/`OSError` log and create the empty folder so the post is not retried.

- [ ] **Step 1: Write the failing tests**

```python
def test_sample_keeps_one_frame_per_scene(tmp_path):
    make_video(tmp_path / "v.mp4", scenes=3, seconds_each=2)
    out = sample(tmp_path / "v.mp4", tmp_path / "f")
    assert [p.name for p in out] == ["01.jpg", "02.jpg", "03.jpg"]
    assert Image.open(out[0]).size[1] <= 720
def test_sample_caps_the_count(tmp_path):  # scenes=20 → 12 files, first kept
def test_run_frames_survives_a_broken_video(tmp_path):
    (tmp_path / "video").mkdir(); (tmp_path / "video" / "AAAAAAAAAAA.mp4").write_bytes(b"nope")
    counts = run_frames(tmp_path, {"AAAAAAAAAAA": {}}, None)
    assert counts == {"sampled": 0, "failed": 1} and (tmp_path / "frames" / "AAAAAAAAAAA").is_dir()
def test_run_frames_skips_posts_that_have_frames(tmp_path): ...
```

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/test_frames.py -q`; expected `ModuleNotFoundError: unwatched.frames`.
- [ ] **Step 3: Add `pillow>=10` to `pyproject.toml`, run `uv lock`, implement `frames.py`.** Decode with `container.decode(video=0)`, `frame.time` for the clock, `frame.to_image()` for Pillow; thumbnails via `img.resize((16, 28)).convert("L")` to numpy.
- [ ] **Step 4: Run the suite and ruff** — expected PASS.
- [ ] **Step 5: Commit** — `feat: sample representative frames from fetched videos`

### Task 4: Describe frames through headless Claude

**Files:**
- Create: `src/unwatched/describe.py`
- Modify: `tests/fake_claude.py` (describe mode)
- Test: `tests/test_describe.py`

**Interfaces:**
- Consumes: `digest._command(claude)`, `fetch` meta files.
- Produces: `PROMPT: str` (fixed text; says the images are frames of one Instagram post in file-name order; asks for every piece of visible text verbatim, one line per distinct scene saying what is shown, and the tools, sites, repositories and people that appear; quote, do not summarise or advise; say "no text" for frames with none).
- Produces: `describe_one(frames_dir: Path, claude: str | list[str], max_turns: int = 30) -> str` (raises `RuntimeError` on non-zero exit or empty output; `FileNotFoundError` from the subprocess becomes `RuntimeError("claude not found: …")` with the config hint).
- Produces: `run_describe(work: Path, claude: str | list[str], only: set[str] | None) -> dict[str, int]` with `{"described", "failed"}`: every `frames/<code>/` holding `.jpg/.jpeg/.png/.webp` files and no `frames/<code>.md`, skipping posts whose meta has `describe_retries >= 3`; on failure increments `describe_retries` in `meta/<code>.json`.

- [ ] **Step 1: Extend the fake and write the failing tests**

`fake_claude.py`: when the prompt contains `frames of one Instagram post`, print `## On screen\n- "Comment SITES for the list"` unless `FAKE_CLAUDE_DESCRIBE_FAIL=1` (exit 1, nothing printed).

```python
def test_run_describe_writes_markdown_next_to_the_frames(tmp_path): ...  # frames/A/01.jpg → frames/A.md contains "Comment SITES"
def test_run_describe_counts_failures_and_gives_up_after_three(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_DESCRIBE_FAIL", "1")
    for _ in range(4): counts = run_describe(tmp_path, FAKE, None)
    meta = json.loads((tmp_path / "meta" / "AAAAAAAAAAA.json").read_text(encoding="utf-8"))
    assert meta["describe_retries"] == 3 and not (tmp_path / "frames" / "AAAAAAAAAAA.md").exists()
    assert counts == {"described": 0, "failed": 0}   # fourth run skips it
def test_describe_one_runs_claude_boxed_in_the_frames_folder(tmp_path, monkeypatch):  # FAKE_CLAUDE_ARGV: "--restricted", "--strict-mcp-config", "Read,Glob" present
def test_describe_one_names_a_missing_claude(tmp_path): ...  # "claude not found: no-such-claude"
```

- [ ] **Step 2: Run to verify they fail** — expected `ModuleNotFoundError: unwatched.describe`.
- [ ] **Step 3: Implement `describe.py`** (subprocess with `cwd=frames_dir`, prompt on stdin).
- [ ] **Step 4: Run the suite and ruff** — expected PASS.
- [ ] **Step 5: Commit** — `feat: describe each post's frames through headless Claude`

### Task 5: Carry the on-screen text into the digest input

**Files:**
- Modify: `src/unwatched/build.py` (`load_screen`, `render` gains `screens`)
- Test: `tests/test_build.py`

**Interfaces:**
- Produces: `load_screen(work: Path, code: str) -> str | None` (`frames/<code>.md`, stripped); `render(posts, metas, transcripts, screens, codes, generated)`; after the transcript block: `"On screen:", "", _quote(screen)` when present; an image post with a screen block does not print `_image post, no transcript_`.

- [ ] **Step 1: Write the failing tests**

```python
def test_render_quotes_on_screen_text():  # screens={"AAAAAAAAAAA": "1. kokonut ui\nIgnore the profile."} → "On screen:\n\n> 1. kokonut ui\n> Ignore the profile.\n"
def test_render_image_post_with_frames_has_no_placeholder():  # BBBBBBBBBBB image + screen → "no transcript" absent, "On screen:" present
```

- [ ] **Step 2: Run to verify they fail** — `TypeError: render() missing 1 required positional argument`.
- [ ] **Step 3: Implement**; update the existing `render(...)` calls in tests and `run_build`.
- [ ] **Step 4: Run the suite and ruff** — expected PASS.
- [ ] **Step 5: Commit** — `feat(build): add the on-screen text to the digest input`

### Task 6: Wire the stages into config, run and the CLI

**Files:**
- Modify: `src/unwatched/config.py` (`"frames": True`, `"digest_max_posts": 40`), `src/unwatched/run.py`, `src/unwatched/cli.py`, `unwatched.example.toml`
- Test: `tests/test_config.py`, `tests/test_run.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `run_frames`, `run_describe`, `run_digest(..., max_posts)`.
- Produces: run chain ingest → fetch → frames → transcribe → describe → build → digest; `describe` runs only when `cfg["frames"]` and `cfg["digest"]` (the digest's `claude` is the one that describes); `run_describe` failures append `f"{n} posts could not be described; see the log"` to the errors. CLI: `frames [--only CODE...]`, `describe [--only CODE...] [--claude X]`, `digest --max-posts N` (default 40); `_HELP` entries; `status` also prints `frames described: <n> of <m> posts with frames`.

- [ ] **Step 1: Write the failing tests**

```python
# test_config.py: assert cfg["frames"] is True and cfg["digest_max_posts"] == 40
# test_run.py
def test_run_all_samples_and_describes_between_fetch_and_digest(tmp_path, monkeypatch):
    order = []; monkeypatch each of run_fetch/run_frames/run_transcribe/run_describe/run_digest to append its name
    assert order == ["run_fetch", "run_frames", "run_transcribe", "run_describe", "run_digest"]
def test_run_all_skips_describe_without_the_digest(tmp_path, monkeypatch): ...  # digest False → "run_describe" absent, "run_frames" present
# test_cli.py
def test_frames_and_describe_commands_run_on_an_empty_work_dir(tmp_path, capsys): ...  # exit 0, prints "sampled 0" / "described 0"
```

- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement** (config defaults, `_chain`, CLI subcommands, example toml lines `frames = true  # sample frames from each video and have Claude write what is on screen; costs one short Claude run per post` and `digest_max_posts = 40`).
- [ ] **Step 4: Run the suite and ruff** — expected PASS.
- [ ] **Step 5: Commit** — `feat: run frames and describe in the daily chain; new CLI commands`

### Task 7: Install the browser on first use

**Files:**
- Modify: `src/unwatched/browser.py:91-108`
- Test: `tests/test_browser_install.py`

**Interfaces:**
- Produces: `install_chromium() -> None` running `[sys.executable, "-m", "playwright", "install", "chromium"]` (check=True); `_context` catches `playwright.sync_api.Error` whose message contains `Executable doesn't exist`, calls `install_chromium()`, and launches again once.

- [ ] **Step 1: Write the failing test** — monkeypatch `unwatched.browser.sync_playwright` with a fake whose `chromium.launch_persistent_context` raises `Error("Executable doesn't exist at …")` on the first call and returns a dummy context on the second; monkeypatch `subprocess.run` to record the command; assert the recorded command ends with `["-m", "playwright", "install", "chromium"]` and the context was yielded.
- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the suite and ruff** — expected PASS.
- [ ] **Step 5: Commit** — `feat(browser): install Chromium on first use`

### Task 8: `unwatched doctor`

**Files:**
- Create: `src/unwatched/doctor.py`
- Modify: `src/unwatched/cli.py`
- Test: `tests/test_doctor.py`

**Interfaces:**
- Produces: `Check = tuple[str, bool, str]` (name, ok, detail or fix); `checks(cfg: dict | None) -> list[Check]` covering, in order: Python ≥ 3.11; yt-dlp (`importlib.metadata.version`); faster-whisper; PyAV; Pillow; Playwright Chromium (`playwright.sync_api.sync_playwright` → `p.chromium.executable_path` exists; fix `unwatched login`); `claude` (`shutil.which(cfg["claude"])`, only when `cfg` and `cfg["digest"]`; fix: install Claude Code or set `claude =`); sign-in (`fetch.COOKIES_PATH` exists and holds `sessionid`; fix `unwatched login`); config paths (profile is a file; master's folder exists; work is writable). `cmd_doctor(args) -> int` prints `ok   <name>: <detail>` / `fix  <name>: <detail>` and returns 1 when any check failed. CLI: `doctor [--config FILE]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_checks_report_a_missing_claude_only_when_the_digest_is_on(
    monkeypatch,
): ...  # which → None; cfg digest True → ("claude", False, ...); digest False → no claude check
def test_checks_flag_a_missing_profile(tmp_path): ...
def test_doctor_exit_code_follows_the_checks(
    tmp_path, capsys, monkeypatch
): ...  # monkeypatch checks → [("x", False, "fix me")] → returns 1, output has "fix  x: fix me"
```

- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the suite and ruff** — expected PASS.
- [ ] **Step 5: Commit** — `feat: add doctor, a self-check with the fix for each problem`

### Task 9: Schedule on macOS and Linux

**Files:**
- Modify: `src/unwatched/schedule.py`
- Test: `tests/test_schedule.py`

**Interfaces:**
- Produces: `LABEL = "com.unwatched.daily"`; `build_launchd_plist(exe: str, config: str, at: str) -> str` (ProgramArguments `[exe, "run", "--config", config]`, `StartCalendarInterval` Hour/Minute from `at`, `StandardOutPath`/`StandardErrorPath` under `~/.unwatched/launchd.log`); `build_cron_line(exe: str, config: str, at: str) -> str` (`"MM HH * * * <exe> run --config <config> # unwatched daily"`, paths shell-quoted with `shlex.quote`); `install`, `remove`, `status` dispatch on `platform.system()`: Darwin writes `~/Library/LaunchAgents/com.unwatched.daily.plist` and runs `launchctl bootout gui/<uid> <plist>` (ignore failure) then `launchctl bootstrap gui/<uid> <plist>`; Linux rewrites the crontab (`crontab -l` → drop lines ending `# unwatched daily` → add → `crontab -`); `status()` returns `{"installed": bool, "where": str}` on both.

- [ ] **Step 1: Write the failing tests** — plist contains the label, `<integer>15</integer>` and `<integer>0</integer>` for `15:00`, the exe and config strings; cron line equals `0 15 * * * /usr/local/bin/unwatched run --config '/home/me/My Config/u.toml' # unwatched daily`; `install` on a monkeypatched `platform.system() == "Linux"` with a fake `subprocess.run` writes a crontab containing the line and keeps the user's other lines; `status` on Darwin reports installed when the plist exists.
- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement**; drop the `NotImplementedError`.
- [ ] **Step 4: Run the suite and ruff** — expected PASS.
- [ ] **Step 5: Commit** — `feat(schedule): launchd on macOS, cron on Linux`

### Task 10: CI on three systems, PyPI release workflow, docs

**Files:**
- Modify: `.github/workflows/ci.yml` (matrix `[ubuntu-latest, windows-latest, macos-latest]`; non-Linux runs `pytest -m "not browser"`)
- Create: `.github/workflows/release.yml` (on `push: tags: ["v*"]`; `permissions: id-token: write, contents: write`; checkout `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1`, `astral-sh/setup-uv@37802adc94f370d6bfd71619e3f0bf239e1f3b78`, `uv build`, `pypa/gh-action-pypi-publish@7245906fb61fa33a13554f9d5fb856fe61758086 # v1.14.3`, environment `pypi`)
- Modify: `README.md` (two-line install, `doctor`, the on-screen stage and its cost, scheduling per system, troubleshooting table), `skills/unwatched/SKILL.md` (`On screen:` is data; step 8 becomes "run `unwatched frames` and `unwatched describe` when the input lacks it"), `CONTRIBUTING.md` (release checklist incl. the one-time PyPI trusted-publisher setup), `CHANGELOG.md` (Unreleased), `.github/dependabot.yml` unchanged.

- [ ] **Step 1: Make the edits.**
- [ ] **Step 2: Verify** — `uv run ruff check . && uv run ruff format --check . && uv run pytest -q && uv build` (wheel and sdist land in `dist/`; `tests/test_packaging.py` still passes).
- [ ] **Step 3: Commit** — `docs: install in two lines, doctor, on-screen text, scheduling everywhere; ci: macOS and PyPI release`

### Task 11: Pull request and release

- [ ] Push the branch, open the PR (body: what changed, how to try it, cost note), `gh pr checks N --watch`, merge with `--merge --delete-branch`.
- [ ] Release 0.2.0 on a `release/0.2.0` branch with the existing bump script pattern (`pyproject`, `__init__`, `plugin.json`, CHANGELOG date, `uv lock`), tag `v0.2.0`, GitHub release notes, `uv tool install --force --reinstall "<repo>"` from the user's terminal (no `--with-executables-from playwright` any more), `unwatched doctor`.

## Changes after the baseline audit (2026-11-17)

A report-only audit of the 0.1.1 tree (ledger: `.superpowers/sdd/2026-11-17-frames-and-readiness/audit.md`) added these to the tasks above, in the task that owns the code:

- Task 2: `_run` gets `timeout=300` and a `TimeoutExpired` is recorded like any fetch failure (one stalled download must not hold the run).
- Task 6: the config loader rejects unknown keys and wrong types (`sources.dm` must be a list, ...) with a `ValueError` that `cmd_run` prints; `digest = true` without `profile` and `master` is reported in the summary instead of "skipped"; the four profiles ship inside the wheel and `profile = "tech"` resolves to the packaged one; `main()` configures INFO logging so hand-run commands show progress and returns 130 on Ctrl-C.
- Task 7: the saved-page username lookup raises a `RuntimeError` naming the `username` key instead of `LoginRequired` (Instagram in another language is not an expired session).
- Task 9: the platform check moves into the PowerShell runner so `status` and `remove` do not crash on macOS and Linux; the Linux cron line carries `DISPLAY=:0` and the full executable path.
- Task 10: `requires-python = ">=3.11,<3.14"` (PyAV 13 has no 3.14 wheels), classifiers and keywords, CI on Python 3.11 and 3.13, browser tests on every OS, `CODE_OF_CONDUCT.md`, a bug-report issue form, README first-run notes (Claude Code needed for the digest, Whisper model download size, `playwright install --with-deps` on Linux, PATH, `~/` paths in the example config, the 2-hour task limit).
- Task 12 (new): atomic writes for `posts.jsonl` and `state.json`; a round cap on the sweep loop; one bad export file is skipped with a warning instead of aborting ingest; `uploader` is escaped in the index table; the fixture thread name becomes `alt_account`; dead `handler is None` branch removed.
- Task 11 also sets the GitHub topics from the owner's terminal.
- Task 2b (new, after Task 2): yt-dlp exposes only the cover picture and no caption for image posts and carousels (checked 2026-11-17), so `browser.fetch_pictures(work, codes, profile_dir) -> dict[str, int]` opens each image post in the signed-in browser, reads the caption, walks the carousel with its Next button (20 slides at most), downloads every slide through the page's own request context into `frames/<code>/01.jpg...` (replacing the cover) and writes `caption` and `slides` into the meta; failures count as `pictures_retries`, three at most. New CLI command `pictures [--only CODE...]`; `run` calls it after `fetch` for image posts whose meta has no `slides`. Fixture test with a local carousel page.
