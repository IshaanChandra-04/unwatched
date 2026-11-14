# unwatched v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python CLI plus Claude skill that collects the reels a person saved or DM'd themselves on Instagram, transcribes them locally, and hands one digest file to Claude every day at 3 pm to update a master document.

**Architecture:** Deterministic stages joined by files under one work directory: `posts.jsonl` (what exists) → `meta/` and `audio/` (yt-dlp) → `transcripts/` (faster-whisper) → `digest-input.md` (one file) → `claude -p` (judgement). Collection sources are the data export, a links file, and live Playwright sweeps of a DM thread and the saved page on a browser profile the user signs into once. A Windows Task Scheduler task runs the whole chain daily.

**Tech Stack:** Python 3.12 (floor 3.11), uv + hatchling, argparse, playwright, yt-dlp, faster-whisper with `av<14`, pytest, ruff, pre-commit, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-12-unwatched-design.md` (revision 2). Read it first; this plan argues from it.

## Global Constraints

- `requires-python = ">=3.11"`; dev and CI on 3.12. Dependencies: `playwright`, `yt-dlp`, `faster-whisper`, `av<14`. Dev: `ruff`, `pytest`, `pre-commit`. Nothing else (no click, rich, pydantic, requests).
- Package `unwatched`, console script `unwatched`, src layout, `uv.lock` committed, every command via `uv run`.
- The tool never asks for, stores, or types a password. Cookies and the browser profile never appear in logs or the repo.
- Exit codes: `0` ok, `2` usage, `3` sign-in required, `4` fetch cap exceeded, `5` digest failed, `1` other. Exit messages are one plain sentence.
- Post record and source shapes exactly as in the spec's data contract. Timestamps are ISO 8601 UTC with a `Z` suffix, seconds precision.
- Fetch defaults: kinds `saved,dm`, cap `300`, delay `3` seconds. Transcribe default model `small`. Schedule default `15:00`, task name `unwatched daily`.
- Commits in Conventional Commits form; every commit message ends with the trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Task 1 shows the form; later tasks say "commit" and mean the same form.
- No network in unit tests. Tests marked `browser` need Chromium and run only where it is installed.
- Ponytail is active: stdlib first, no helper that one caller uses, no option nobody asked for.

## Review Focus

Failure modes the spec implies but no obvious test covers. Each has a test pinned to the owning task below.

1. An export zip whose files sit under a top-level folder (`instagram-name-2026-11-14/your_instagram_activity/...`) or split across several zips must still be discovered. (Task 4)
2. A DM message that carries the reel link in its `content` text rather than `share.link`, and a `share` object without a `link`, must yield the right codes and crash on neither. (Task 4)
3. Export timestamps are seconds in saved/liked files and milliseconds in messages; both must become the same ISO form. (Task 4)
4. A carousel comes back from yt-dlp as a playlist with mixed image and video entries; `media_type` must be `video` when any entry has a duration and `image` otherwise. (Task 7)
5. A scheduled task whose executable or config path contains spaces must still register and run. (Task 11)

---

### Task 1: Repository scaffold, tooling, CI

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `.github/dependabot.yml`, `LICENSE`, `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `src/unwatched/__init__.py`, `tests/__init__.py`, `tests/conftest.py`
- Already present: `docs/superpowers/specs/2026-11-12-unwatched-design.md`, `docs/superpowers/plans/2026-11-14-unwatched-v1.md`

**Interfaces:**
- Produces: `unwatched.__version__ == "0.1.0"`; pytest marker `browser`; `uv run unwatched` entry point (`unwatched.cli:main`, defined in Task 5).

- [ ] **Step 1: Write `pyproject.toml`**

Exact values: `[project] name = "unwatched"`, `version = "0.1.0"`, `description = "Turn the reels you saved or sent yourself into a document you will actually read."`, `license = "MIT"`, `requires-python = ">=3.11"`, `dependencies = ["playwright>=1.50", "yt-dlp>=2025.1.1", "faster-whisper>=1.1", "av<14"]`, `[project.scripts] unwatched = "unwatched.cli:main"`, `[build-system] requires = ["hatchling"]`, `build-backend = "hatchling.build"`, `[tool.hatch.build.targets.wheel] packages = ["src/unwatched"]`, `[tool.hatch.build.targets.wheel.force-include] "skills/unwatched/SKILL.md" = "unwatched/skill/SKILL.md"`, `[dependency-groups] dev = ["pytest>=8", "ruff>=0.8", "pre-commit>=4"]`, `[tool.ruff] line-length = 100`, `target-version = "py311"`, `[tool.ruff.lint] select = ["E", "F", "I", "UP", "B"]`, `[tool.pytest.ini_options] testpaths = ["tests"]`, `markers = ["browser: needs a Playwright Chromium install"]`.

- [ ] **Step 2: Write the support files**

`.gitignore`: `.venv/`, `__pycache__/`, `*.pyc`, `dist/`, `work/`, `unwatched.toml`, `.pytest_cache/`, `.ruff_cache/`.
`.pre-commit-config.yaml`: ruff-pre-commit (`ruff` with `--fix`, `ruff-format`) and pre-commit-hooks (`trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files`).
`.github/workflows/ci.yml`: on `push` and `pull_request`; matrix `os: [ubuntu-latest, windows-latest]`, Python `3.12`; steps: checkout, `astral-sh/setup-uv`, `uv sync --all-groups`, `uv run ruff check .`, `uv run ruff format --check .`, on ubuntu `uv run playwright install --with-deps chromium` then `uv run pytest`, on windows `uv run pytest -m "not browser"`.
`.github/dependabot.yml`: `pip` and `github-actions`, weekly.
`LICENSE`: MIT, year 2026, copyright holder the owner's name as they give it (placeholder `<owner>` until Task 16).
`README.md`: title and the one-line description only (filled in Task 14). `CHANGELOG.md`: Keep a Changelog header with an `Unreleased` section. `CONTRIBUTING.md`: uv setup, `uv run pytest`, pre-commit install, branch-and-PR rule, Conventional Commits. `SECURITY.md`: report privately via GitHub security advisories; never include cookies or profile files in reports.
`src/unwatched/__init__.py`: `__version__ = "0.1.0"`. `tests/conftest.py`: empty for now.

- [ ] **Step 3: Initialise and verify**

Run in `C:\Users\<you>\Documents\Claude Plugin Repos\unwatched`:
`git init -b main`, `uv sync --all-groups`, `uv run ruff check .`, `uv run pytest`.
Expected: ruff reports no errors; pytest reports `no tests ran` with exit code 5 (acceptable here only).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: scaffold unwatched package, tooling and CI" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Shortcodes and URL parsing

**Files:**
- Create: `src/unwatched/shortcode.py`
- Test: `tests/test_shortcode.py`

**Interfaces:**
- Produces: `ALPHABET: str` (Instagram's 64 characters `A-Z a-z 0-9 - _` in that order); `media_id_to_shortcode(media_id: int) -> str`; `shortcode_from_cache_key(key: str) -> str | None` (URL-unquotes, base64-decodes, keeps the digits before any `_`, returns `None` on anything else); `codes_from_text(text: str) -> list[str]` (pattern `instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)`, unique, in order of first appearance); `url_for(code: str) -> str` returning `https://www.instagram.com/p/<code>/`.

- [ ] **Step 1: Write the failing tests**

```python
import base64
from urllib.parse import quote
from unwatched.shortcode import (ALPHABET, codes_from_text, media_id_to_shortcode,
                                 shortcode_from_cache_key, url_for)

def test_alphabet_is_instagram_order():
    assert len(ALPHABET) == 64 and ALPHABET[0] == "A" and ALPHABET[26] == "a" and ALPHABET[52] == "0" and ALPHABET[62:] == "-_"

def test_media_id_to_shortcode_small_values():
    assert media_id_to_shortcode(0) == "A"
    assert media_id_to_shortcode(63) == "_"
    assert media_id_to_shortcode(64) == "BA"

def test_cache_key_decodes_to_shortcode():
    key = quote(base64.b64encode(b"3700000000000000000_123").decode())
    assert shortcode_from_cache_key(key) == media_id_to_shortcode(3700000000000000000)

def test_cache_key_garbage_is_none():
    assert shortcode_from_cache_key("not-base64!!") is None
    assert shortcode_from_cache_key(base64.b64encode(b"abc").decode()) is None

def test_codes_from_text_variants_and_dedupe():
    text = ("https://www.instagram.com/p/AAAAAAAAAAA/ x https://instagram.com/reel/BBBBBBBBBBB/?igsh=1 "
            "https://www.instagram.com/reels/CCCCCCCCCCC https://www.instagram.com/p/AAAAAAAAAAA/")
    assert codes_from_text(text) == ["AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC"]

def test_url_for():
    assert url_for("AAAAAAAAAAA") == "https://www.instagram.com/p/AAAAAAAAAAA/"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_shortcode.py -v`. Expected: FAIL, `ModuleNotFoundError: unwatched.shortcode`.

- [ ] **Step 3: Implement `shortcode.py`**

Signatures as in Interfaces. `media_id_to_shortcode`: repeated divmod by 64, most significant first; `0` yields `"A"`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_shortcode.py -v`. Expected: 6 passed.

- [ ] **Step 5: Commit** — `feat: shortcode and URL parsing`

---

### Task 3: Post store and run state

**Files:**
- Create: `src/unwatched/posts.py`, `src/unwatched/state.py`
- Test: `tests/test_posts.py`, `tests/test_state.py`

**Interfaces:**
- Produces (`posts.py`): `load_posts(work: Path) -> dict[str, dict]` (empty dict when `work/posts.jsonl` is missing); `save_posts(work: Path, posts: dict[str, dict]) -> None` (one JSON object per line, sorted by code, creates `work/`); `add_source(posts: dict[str, dict], code: str, source: dict, url: str | None = None, local_media: str | None = None) -> bool` (creates the record on first sight with `url` defaulting to `url_for(code)`, appends the source unless an identical one is present, keeps `first_seen` as the minimum source `ts`, returns `True` when the post is new); `new_since(posts: dict[str, dict], since: str | None) -> list[str]` (codes with `first_seen > since`, all codes when `since` is `None`, sorted by `first_seen`); `now_iso() -> str`.
- Produces (`state.py`): `load_state(work: Path) -> dict` with keys `last_run`, `last_digest`, `last_error`, `last_summary` defaulting to `None`; `save_state(work: Path, state: dict) -> None` to `work/state.json`.

- [ ] **Step 1: Write the failing tests**

```python
from unwatched.posts import add_source, load_posts, new_since, save_posts

SRC_A = {"kind": "saved", "name": "saved", "via": "export", "ts": "2025-10-31T08:40:00Z"}
SRC_B = {"kind": "dm", "name": "kungfookah", "via": "live", "ts": "2025-10-30T11:40:00Z"}

def test_add_source_creates_then_merges_and_keeps_earliest_first_seen():
    posts = {}
    assert add_source(posts, "AAAAAAAAAAA", SRC_A) is True
    assert add_source(posts, "AAAAAAAAAAA", SRC_B) is False
    assert add_source(posts, "AAAAAAAAAAA", SRC_B) is False
    rec = posts["AAAAAAAAAAA"]
    assert rec["url"] == "https://www.instagram.com/p/AAAAAAAAAAA/"
    assert rec["sources"] == [SRC_A, SRC_B]
    assert rec["first_seen"] == "2025-10-30T11:40:00Z"
    assert rec["local_media"] is None

def test_roundtrip_and_missing_file(tmp_path):
    assert load_posts(tmp_path) == {}
    posts = {}
    add_source(posts, "BBBBBBBBBBB", SRC_A)
    save_posts(tmp_path, posts)
    assert load_posts(tmp_path) == posts
    assert (tmp_path / "posts.jsonl").read_text(encoding="utf-8").count("\n") == 1

def test_new_since():
    posts = {}
    add_source(posts, "AAAAAAAAAAA", SRC_A)
    add_source(posts, "BBBBBBBBBBB", SRC_B)
    assert new_since(posts, "2025-10-31T00:00:00Z") == ["AAAAAAAAAAA"]
    assert new_since(posts, None) == ["BBBBBBBBBBB", "AAAAAAAAAAA"]
```

```python
from unwatched.state import load_state, save_state

def test_state_defaults_and_roundtrip(tmp_path):
    state = load_state(tmp_path)
    assert state == {"last_run": None, "last_digest": None, "last_error": None, "last_summary": None}
    state["last_run"] = "2026-11-14T15:00:00Z"
    save_state(tmp_path, state)
    assert load_state(tmp_path)["last_run"] == "2026-11-14T15:00:00Z"
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_posts.py tests/test_state.py -v`. Expected: import errors.
- [ ] **Step 3: Implement `posts.py` and `state.py`** with the signatures above. A source with `ts` `None` does not move `first_seen`; a brand-new post with a `None` ts gets `first_seen = now_iso()`.
- [ ] **Step 4: Run to verify pass** — Expected: 4 passed.
- [ ] **Step 5: Commit** — `feat: post store and run state`

---

### Task 4: Ingest from export, links file, and seeding

**Files:**
- Create: `src/unwatched/ingest.py`, `tests/fixtures/export/your_instagram_activity/saved/saved_posts.json`, `.../likes/liked_posts.json`, `.../messages/inbox/kungfookah_123/message_1.json`, `.../content/archived_posts.json`, `tests/fixtures/export/media/posts/202510/vid.mp4` (empty file), `tests/fixtures/links.md`
- Test: `tests/test_ingest.py`

**Interfaces:**
- Consumes: Task 2 `codes_from_text`, Task 3 `add_source`, `load_posts`, `save_posts`.
- Produces: `Found = tuple[str, dict, str | None]` meaning `(code, source, local_media)`; `fix_text(s: str) -> str` (latin-1 → utf-8 round trip, original on failure); `iso_from_epoch(value: int | float, unit: str) -> str` with `unit` `"s"` or `"ms"`; `iter_export_files(path: Path) -> Iterator[tuple[str, bytes]]` yielding `(relative_posix_name, data)` for every `*.json` in a folder or zip; `parse_saved(data: dict, name: str) -> list[Found]`, `parse_liked(data: dict) -> list[Found]`, `parse_messages(data: dict) -> list[Found]`, `parse_archived(data: dict, media_root: str) -> list[Found]`; `ingest_export(path: Path) -> list[Found]` dispatching by file name suffix (`saved_posts.json` → saved named `saved`; `saved_collections.json` → saved named by the nearest `title` or `collection`; `liked_posts.json`; `archived_posts.json`; any `messages/inbox/*/message_*.json`); `ingest_links(path: Path) -> list[Found]` (kind `links`, name = file name, via `file`, ts `None`); `apply(work: Path, found: list[Found], seen: bool = False) -> dict[str, int]` merging into the store, returning counts per `kind:name`, and when `seen` is true also writing `work/meta/<code>.json` as `{"code": code, "skipped": "seeded"}` for every new code and setting `state.last_digest = now_iso()` if it was `None`.
- Message parsing rule: for each message, codes come from `share.link` if present plus `codes_from_text(content)`; `text` is `fix_text(share.share_text)` when present; source name is `data["title"]` or `"thread"`; ts from `timestamp_ms` with unit `ms`. Saved and liked use unit `s`.
- Archived rule: each `media[]` item yields code `archived-<creation_timestamp>`, url `None`, `local_media = media_root + "/" + uri`, source kind `archived`, name `archive`, text `fix_text(title)`. For a zip export, `apply` extracts `local_media` to `work/archived/<code><suffix>` and stores that path instead.

- [ ] **Step 1: Write the fixtures**

`saved_posts.json`: `{"saved_saved_media": [{"title": "authorA", "string_map_data": {"Saved on": {"href": "https://www.instagram.com/p/AAAAAAAAAAA/", "timestamp": 1761900000}}}, {"title": "authorB", "string_map_data": {"Saved on": {"href": "https://www.instagram.com/reel/BBBBBBBBBBB/", "timestamp": 1761903600}}}]}`
`liked_posts.json`: `{"likes_media_likes": [{"title": "authorC", "string_list_data": [{"href": "https://www.instagram.com/p/CCCCCCCCCCC/", "timestamp": 1761907200}]}]}`
`message_1.json`: `{"participants": [{"name": "kungfookah"}, {"name": "me"}], "title": "kungfookah", "messages": [{"sender_name": "me", "timestamp_ms": 1761910800000, "share": {"link": "https://www.instagram.com/reel/AAAAAAAAAAA/", "share_text": "caf\u00c3\u00a9 tips", "original_content_owner": "authorA"}}, {"sender_name": "me", "timestamp_ms": 1761914400000, "content": "look https://www.instagram.com/p/DDDDDDDDDDD/?igsh=abc"}, {"sender_name": "me", "timestamp_ms": 1761918000000, "share": {"share_text": "no link here"}}]}`
`archived_posts.json`: `{"ig_archived_post_media": [{"media": [{"uri": "media/posts/202510/vid.mp4", "creation_timestamp": 1761921600, "title": "my old post"}]}]}`
`links.md`: two lines containing `https://www.instagram.com/p/EEEEEEEEEEE/` and `https://www.instagram.com/reel/AAAAAAAAAAA/`.

- [ ] **Step 2: Write the failing tests**

```python
import json, shutil, zipfile
from pathlib import Path
from unwatched.ingest import apply, fix_text, ingest_export, ingest_links, iso_from_epoch
from unwatched.posts import load_posts
from unwatched.state import load_state

FIX = Path(__file__).parent / "fixtures" / "export"

def test_fix_text_repairs_mojibake_and_leaves_plain_text():
    assert fix_text("caf\u00c3\u00a9 tips") == "café tips"
    assert fix_text("plain") == "plain"

def test_iso_from_epoch_units():
    assert iso_from_epoch(1761900000, "s") == "2025-10-31T08:40:00Z"
    assert iso_from_epoch(1761910800000, "ms") == "2025-10-31T11:40:00Z"

def test_ingest_export_folder_finds_every_source():
    found = ingest_export(FIX)
    by_code = {}
    for code, src, _ in found:
        by_code.setdefault(code, []).append(src["kind"])
    assert by_code["AAAAAAAAAAA"] == ["saved", "dm"]
    assert by_code["BBBBBBBBBBB"] == ["saved"]
    assert by_code["CCCCCCCCCCC"] == ["liked"]
    assert by_code["DDDDDDDDDDD"] == ["dm"]
    assert by_code["archived-1761921600"] == ["archived"]
    dm = [s for c, s, _ in found if c == "AAAAAAAAAAA" and s["kind"] == "dm"][0]
    assert dm["name"] == "kungfookah" and dm["text"] == "café tips" and dm["ts"] == "2025-10-31T11:40:00Z"

def test_ingest_export_zip_with_nested_top_folder(tmp_path):
    zpath = tmp_path / "export.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        for p in FIX.rglob("*"):
            if p.is_file():
                z.write(p, "instagram-me-2026/" + p.relative_to(FIX).as_posix())
    codes = {c for c, _, _ in ingest_export(zpath)}
    assert codes == {"AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC", "DDDDDDDDDDD", "archived-1761921600"}

def test_ingest_links_file():
    found = ingest_links(Path(__file__).parent / "fixtures" / "links.md")
    assert [c for c, _, _ in found] == ["EEEEEEEEEEE", "AAAAAAAAAAA"]
    assert found[0][1] == {"kind": "links", "name": "links.md", "via": "file", "ts": None}

def test_apply_merges_counts_and_archived_media(tmp_path):
    counts = apply(tmp_path, ingest_export(FIX))
    posts = load_posts(tmp_path)
    assert len(posts) == 5 and counts["dm:kungfookah"] == 2 and counts["saved:saved"] == 2
    assert posts["archived-1761921600"]["url"] is None
    assert Path(posts["archived-1761921600"]["local_media"]).name == "vid.mp4"

def test_apply_seen_marks_meta_and_sets_last_digest(tmp_path):
    apply(tmp_path, ingest_links(Path(__file__).parent / "fixtures" / "links.md"), seen=True)
    assert json.loads((tmp_path / "meta" / "EEEEEEEEEEE.json").read_text())["skipped"] == "seeded"
    assert load_state(tmp_path)["last_digest"] is not None
```

- [ ] **Step 3: Run to verify failure** — `uv run pytest tests/test_ingest.py -v`. Expected: import error.
- [ ] **Step 4: Implement `ingest.py`** with the Interfaces above. Discovery matches on the file name's tail (`endswith`), never its prefix, so nested folders and multi-part zips work. `iter_export_files` yields only `.json` files; archived media is read from the same zip or folder on demand in `apply`.
- [ ] **Step 5: Run to verify pass** — Expected: 7 passed.
- [ ] **Step 6: Commit** — `feat: ingest export, links file and seeding`

---

### Task 5: Config and CLI skeleton

**Files:**
- Create: `src/unwatched/config.py`, `src/unwatched/cli.py`, `unwatched.example.toml`
- Test: `tests/test_config.py`, `tests/test_cli.py`

**Interfaces:**
- Produces (`config.py`): `DEFAULTS: dict` = `{"work": "work", "profile": None, "master": None, "digest": False, "username": None, "sources": {"dm": [], "saved": False, "links": [], "export": []}, "fetch": {"kinds": ["saved", "dm"], "max": 300, "delay": 3}, "transcribe": {"model": "small", "language": "en"}}`; `load_config(path: Path | None) -> dict` deep-merging the TOML over `DEFAULTS` (missing path → defaults). Paths in the config resolve relative to the config file's folder.
- Produces (`cli.py`): `main(argv: list[str] | None = None) -> int`; subcommands `status`, `ingest`, `fetch`, `transcribe`, `build`, `digest`, `run`, `schedule`, `login`; constants `EXIT_LOGIN = 3`, `EXIT_CAP = 4`, `EXIT_DIGEST = 5`. Every subcommand takes `--work PATH` (default `work`). This task wires only `status` and `ingest [EXPORT...] [--links FILE]... [--seen]`; later tasks add their own.
- `status` prints `last run: <ts or never>`, `last digest: <ts or never>`, `posts: <n>`, and `action needed: <last_error>` when set.

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path
from unwatched.config import DEFAULTS, load_config

def test_defaults_when_no_file():
    cfg = load_config(None)
    assert cfg["fetch"] == {"kinds": ["saved", "dm"], "max": 300, "delay": 3}
    assert cfg["digest"] is False and cfg["transcribe"]["model"] == "small"

def test_example_config_parses_and_resolves_paths(tmp_path):
    (tmp_path / "unwatched.toml").write_text(
        'work = "w"\nprofile = "profiles/tech.md"\ndigest = true\n[sources]\ndm = ["https://www.instagram.com/direct/t/1/"]\nsaved = true\n[fetch]\nkinds = ["saved", "dm"]\nmax = 50\n', encoding="utf-8")
    cfg = load_config(tmp_path / "unwatched.toml")
    assert cfg["work"] == str(tmp_path / "w") and cfg["profile"] == str(tmp_path / "profiles" / "tech.md")
    assert cfg["digest"] is True and cfg["fetch"]["max"] == 50 and cfg["fetch"]["delay"] == 3
    assert cfg["sources"]["dm"] == ["https://www.instagram.com/direct/t/1/"] and cfg["sources"]["saved"] is True
```

```python
from pathlib import Path
from unwatched.cli import main

FIX = Path(__file__).parent / "fixtures"

def test_ingest_then_status(tmp_path, capsys):
    assert main(["ingest", str(FIX / "export"), "--links", str(FIX / "links.md"), "--work", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "dm:kungfookah: 2" in out and "links:links.md: 2" in out
    assert main(["status", "--work", str(tmp_path)]) == 0
    assert "posts: 6" in capsys.readouterr().out

def test_ingest_requires_a_source(tmp_path, capsys):
    assert main(["ingest", "--work", str(tmp_path)]) == 2
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_config.py tests/test_cli.py -v`.
- [ ] **Step 3: Implement `config.py`, `cli.py` (status + ingest), and `unwatched.example.toml`** (the spec's sample, with placeholder paths and `digest = false`). `main` returns the exit code; a `__main__` guard calls `sys.exit(main())`.
- [ ] **Step 4: Run to verify pass** — Expected: 4 passed. Also `uv run unwatched --help` lists the nine subcommands.
- [ ] **Step 5: Commit** — `feat: config loading and CLI skeleton with ingest and status`

---

### Task 6: Build the digest input

**Files:**
- Create: `src/unwatched/build.py`
- Modify: `src/unwatched/cli.py` (add `build --out PATH [--new-only]`)
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: Task 3 store and `new_since`, Task 3 state (`last_digest`).
- Produces: `load_meta(work: Path, code: str) -> dict` (empty dict when missing); `load_transcript(work: Path, code: str) -> str | None`; `render(posts: dict, metas: dict[str, dict], transcripts: dict[str, str | None], codes: list[str], generated: str) -> str`; `run_build(work: Path, out: Path, new_only: bool) -> int` returning the number of posts written (new_only uses `new_since(posts, state["last_digest"])`).
- Render format, exactly: line 1 `# unwatched digest input`; line 3 `Generated <generated> · <n> posts`; a table with header `| Date | Author | Type | Link | Sources |`; then per post `## <code> · @<uploader or "unknown"> · <first_seen date>`, `Link: <url or "(archived post, no link)">`, `Sources: <kind> (<name>, <via>)` joined by `; `, `Caption: <caption or source text or "(none)">`, blank line, then either `Transcript:` + blank + text, or `_image post, no transcript_`, or `_video, not transcribed yet_` when meta says video but no transcript exists. Date in the table is `first_seen[:10]`; Type is meta `media_type` or `?`.

- [ ] **Step 1: Write the failing tests**

```python
from unwatched.build import render

POSTS = {"AAAAAAAAAAA": {"code": "AAAAAAAAAAA", "url": "https://www.instagram.com/p/AAAAAAAAAAA/", "first_seen": "2025-10-31T08:40:00Z", "local_media": None,
                         "sources": [{"kind": "saved", "name": "saved", "via": "export", "ts": "2025-10-31T08:40:00Z"}, {"kind": "dm", "name": "kungfookah", "via": "live", "ts": None, "text": "café tips"}]},
         "BBBBBBBBBBB": {"code": "BBBBBBBBBBB", "url": "https://www.instagram.com/p/BBBBBBBBBBB/", "first_seen": "2025-11-01T00:00:00Z", "local_media": None, "sources": []}}

def test_render_video_with_transcript_and_image_without():
    out = render(POSTS, {"AAAAAAAAAAA": {"uploader": "authorA", "caption": "Build this", "media_type": "video"}, "BBBBBBBBBBB": {"media_type": "image"}},
                 {"AAAAAAAAAAA": "Hello world.", "BBBBBBBBBBB": None}, ["AAAAAAAAAAA", "BBBBBBBBBBB"], "2026-11-14T15:00:00Z")
    assert out.splitlines()[0] == "# unwatched digest input"
    assert "Generated 2026-11-14T15:00:00Z · 2 posts" in out
    assert "| 2025-10-31 | authorA | video | https://www.instagram.com/p/AAAAAAAAAAA/ | saved: saved; dm: kungfookah |" in out
    assert "## AAAAAAAAAAA · @authorA · 2025-10-31" in out and "Caption: Build this" in out and "Transcript:\n\nHello world." in out
    assert "## BBBBBBBBBBB · @unknown · 2025-11-01" in out and "_image post, no transcript_" in out

def test_render_video_without_transcript_yet():
    out = render(POSTS, {"AAAAAAAAAAA": {"media_type": "video"}}, {"AAAAAAAAAAA": None}, ["AAAAAAAAAAA"], "x")
    assert "_video, not transcribed yet_" in out and "Caption: café tips" in out
```

- [ ] **Step 2: Run to verify failure.** — [ ] **Step 3: Implement `build.py` and the `build` subcommand.** — [ ] **Step 4: Run to verify pass** — `uv run pytest tests/test_build.py -v`, 2 passed; `uv run unwatched build --work <tmp> --out <tmp>/digest-input.md` on a Task 5 ingest writes a file. — [ ] **Step 5: Commit** — `feat: render digest input`

---

### Task 7: Fetch metadata and audio with yt-dlp

**Files:**
- Create: `src/unwatched/fetch.py`, `tests/fake_ytdlp.py`
- Modify: `src/unwatched/cli.py` (add `fetch` with `--kinds`, `--thread`, `--since`, `--max`, `--delay`, `--only`, `--cookies`, `--ytdlp`)
- Test: `tests/test_fetch.py`

**Interfaces:**
- Consumes: Task 3 store; Task 9 later supplies the cookies file path (fetch only takes `cookies: Path | None`).
- Produces: `select(posts: dict, kinds: set[str], threads: set[str] | None, since: str | None, only: set[str] | None) -> list[str]` (a post qualifies when any source matches kind, and thread when given; sorted by `first_seen`; `only` bypasses every other filter); `pending(work: Path, codes: list[str]) -> list[str]` (codes without `work/meta/<code>.json`); `trim_meta(code: str, info: dict) -> dict` with keys `code, uploader, caption, upload_date, duration, media_type, error`; `fetch_one(code: str, url: str, work: Path, cookies: Path | None, ytdlp: str = "yt-dlp") -> dict` (writes `work/meta/<code>.json`, downloads `work/audio/<code>.m4a` when `media_type == "video"`, never raises: failures become `error`); `run_fetch(work: Path, codes: list[str], cookies: Path | None, delay: float, ytdlp: str = "yt-dlp") -> dict[str, int]` with `fetched` and `failed`.
- `trim_meta` rule: `info["_type"] == "playlist"` → look at `entries`: `media_type = "video"` if any entry has a truthy `duration`, else `"image"`; `uploader` and `description` from the playlist; `duration` = max entry duration. Otherwise `media_type = "video"` if `info.get("duration")` else `"image"`. `caption = description`, `upload_date` kept as yt-dlp gives it (`YYYYMMDD`).
- yt-dlp invocations: metadata `[ytdlp, "--dump-single-json", "--no-warnings", "--no-playlist"?]` is wrong for carousels, so use `[ytdlp, "--dump-single-json", "--no-warnings", "--flat-playlist", url]` plus `--cookies <file>` when given; audio `[ytdlp, "-x", "--audio-format", "m4a", "--no-warnings", "-o", str(work / "audio" / f"{code}.%(ext)s"), url]` plus cookies. Archived posts (`url` is `None`, `local_media` set) skip yt-dlp: meta `{"media_type": "video", "local": True}`.
- CLI: selection → `pending` → if `len(todo) > max` print `selected <n> posts, cap is <max>; rerun with --max <n> to continue` and return `EXIT_CAP` before any network; else `run_fetch`. Cookies default: `work.parent / "cookies.txt"` if it exists (Task 9 writes it there), else none.

- [ ] **Step 1: Write `tests/fake_ytdlp.py`**

A script that, given `--dump-single-json`, prints the JSON held in env `FAKE_YTDLP_JSON`; given `-x`, writes an empty file at the `-o` template with `%(ext)s` replaced by `m4a`; given env `FAKE_YTDLP_FAIL=1`, exits 1 with `ERROR: login required` on stderr.

- [ ] **Step 2: Write the failing tests**

```python
import json, os, sys
from pathlib import Path
from unwatched.fetch import fetch_one, select, trim_meta
from unwatched.posts import add_source

FAKE = [sys.executable, str(Path(__file__).parent / "fake_ytdlp.py")]

def _posts():
    p = {}
    add_source(p, "AAAAAAAAAAA", {"kind": "saved", "name": "saved", "via": "export", "ts": "2025-10-31T08:40:00Z"})
    add_source(p, "BBBBBBBBBBB", {"kind": "dm", "name": "kungfookah", "via": "live", "ts": "2025-11-01T00:00:00Z"})
    add_source(p, "CCCCCCCCCCC", {"kind": "liked", "name": "likes", "via": "export", "ts": "2025-11-02T00:00:00Z"})
    add_source(p, "DDDDDDDDDDD", {"kind": "dm", "name": "other", "via": "live", "ts": "2025-11-03T00:00:00Z"})
    return p

def test_select_by_kind_thread_since_and_only():
    p = _posts()
    assert select(p, {"saved", "dm"}, None, None, None) == ["AAAAAAAAAAA", "BBBBBBBBBBB", "DDDDDDDDDDD"]
    assert select(p, {"dm"}, {"kungfookah"}, None, None) == ["BBBBBBBBBBB"]
    assert select(p, {"saved", "dm"}, None, "2025-11-02T00:00:00Z", None) == ["DDDDDDDDDDD"]
    assert select(p, {"saved"}, None, None, {"CCCCCCCCCCC"}) == ["CCCCCCCCCCC"]

def test_trim_meta_video_image_and_carousel():
    assert trim_meta("A", {"uploader": "u", "description": "d", "upload_date": "20251031", "duration": 42.0})["media_type"] == "video"
    assert trim_meta("A", {"uploader": "u", "description": "d"})["media_type"] == "image"
    car = trim_meta("A", {"_type": "playlist", "uploader": "u", "description": "d", "entries": [{"duration": None}, {"duration": 12.5}]})
    assert car["media_type"] == "video" and car["duration"] == 12.5
    assert trim_meta("A", {"_type": "playlist", "entries": [{}, {}]})["media_type"] == "image"

def test_fetch_one_video_downloads_audio(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_YTDLP_JSON", json.dumps({"uploader": "u", "description": "d", "duration": 10}))
    meta = fetch_one("AAAAAAAAAAA", "https://www.instagram.com/p/AAAAAAAAAAA/", tmp_path, None, ytdlp=FAKE)
    assert meta["media_type"] == "video" and meta["error"] is None
    assert (tmp_path / "audio" / "AAAAAAAAAAA.m4a").exists() and (tmp_path / "meta" / "AAAAAAAAAAA.json").exists()

def test_fetch_one_failure_is_recorded_not_raised(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_YTDLP_FAIL", "1")
    meta = fetch_one("BBBBBBBBBBB", "https://www.instagram.com/p/BBBBBBBBBBB/", tmp_path, None, ytdlp=FAKE)
    assert "login required" in meta["error"]
```

`ytdlp` therefore accepts a `str` or a `list[str]` command prefix.

- [ ] **Step 3: Run to verify failure.** — [ ] **Step 4: Implement `fetch.py` and the `fetch` subcommand.** — [ ] **Step 5: Run to verify pass** — 4 passed. Add a CLI test in `tests/test_cli.py`: after ingesting the fixture export with 5 posts, `main(["fetch", "--work", w, "--max", "1", "--ytdlp", ...])` returns `4` and creates no `meta/` files. — [ ] **Step 6: Commit** — `feat: fetch metadata and audio with yt-dlp, capped and resumable`

---

### Task 8: Transcribe with faster-whisper

**Files:**
- Create: `src/unwatched/transcribe.py`
- Modify: `src/unwatched/cli.py` (add `transcribe --model --language --only`)
- Test: `tests/test_transcribe.py`

**Interfaces:**
- Produces: `audio_path(work: Path, code: str, posts: dict) -> Path | None` (`work/audio/<code>.m4a` if present, else the post's `local_media` if present, else `None`); `todo(work: Path, posts: dict, only: set[str] | None) -> list[str]` (codes with an audio path and no `work/transcripts/<code>.txt`, or every code in `only` that has an audio path); `transcribe_file(path: Path, model: str, language: str | None) -> str` (lazy-imports `faster_whisper`, loads `WhisperModel(model, device="cpu", compute_type="int8")` once per process, `beam_size=5`, `vad_filter=True`, `condition_on_previous_text=False`, joins segment texts with newlines); `run_transcribe(work: Path, posts: dict, model: str, language: str | None, only: set[str] | None) -> int` writing `work/transcripts/<code>.txt` and returning the count.

- [ ] **Step 1: Write the failing tests** (no model is loaded in tests)

```python
from unwatched.transcribe import audio_path, todo
from unwatched.posts import add_source

def test_todo_skips_done_and_forces_only(tmp_path):
    posts = {}
    add_source(posts, "AAAAAAAAAAA", {"kind": "dm", "name": "t", "via": "live", "ts": None})
    add_source(posts, "BBBBBBBBBBB", {"kind": "dm", "name": "t", "via": "live", "ts": None})
    add_source(posts, "CCCCCCCCCCC", {"kind": "dm", "name": "t", "via": "live", "ts": None})
    (tmp_path / "audio").mkdir(); (tmp_path / "transcripts").mkdir()
    (tmp_path / "audio" / "AAAAAAAAAAA.m4a").touch(); (tmp_path / "audio" / "BBBBBBBBBBB.m4a").touch()
    (tmp_path / "transcripts" / "BBBBBBBBBBB.txt").write_text("done")
    assert todo(tmp_path, posts, None) == ["AAAAAAAAAAA"]
    assert todo(tmp_path, posts, {"BBBBBBBBBBB", "CCCCCCCCCCC"}) == ["BBBBBBBBBBB"]
    assert audio_path(tmp_path, "CCCCCCCCCCC", posts) is None

def test_audio_path_prefers_local_media_for_archived(tmp_path):
    posts = {"archived-1": {"code": "archived-1", "url": None, "sources": [], "first_seen": "x", "local_media": str(tmp_path / "v.mp4")}}
    (tmp_path / "v.mp4").touch()
    assert audio_path(tmp_path, "archived-1", posts) == tmp_path / "v.mp4"
```

- [ ] **Step 2: Run to verify failure.** — [ ] **Step 3: Implement `transcribe.py` and the subcommand.** — [ ] **Step 4: Run to verify pass** — 2 passed. — [ ] **Step 5: Commit** — `feat: local transcription with faster-whisper`

---

### Task 9: Browser sign-in, DM and saved sweeps, cookie export

**Files:**
- Create: `src/unwatched/browser.py`, `tests/fixtures/dm_thread.html`, `tests/fixtures/saved_grid.html`
- Modify: `src/unwatched/cli.py` (add `login`; add `--dm URL`, `--saved`, `--full` to `ingest`; map `LoginRequired` to `EXIT_LOGIN` with the message `sign-in expired, run: unwatched login`)
- Test: `tests/test_browser.py` (all marked `browser`)

**Interfaces:**
- Consumes: Task 2 `shortcode_from_cache_key`, `codes_from_text`; Task 4 `Found`, `apply`.
- Produces: `PROFILE_DIR = Path.home() / ".unwatched" / "browser-profile"`; `class LoginRequired(Exception)`; `login(profile_dir: Path = PROFILE_DIR, timeout_s: int = 600) -> bool` (headful persistent context, `goto("https://www.instagram.com/")`, polls every 2 s for a cookie named `sessionid` on an `instagram.com` domain, closes, returns whether it appeared); `export_cookies(profile_dir: Path, out: Path) -> Path` (Netscape `cookies.txt` of instagram.com cookies, written with mode `0o600` where supported); `codes_from_srcs(srcs: list[str]) -> list[str]` (pure: shortcodes from `ig_cache_key=` query values, unique, in order); `sweep_dm(url: str, known: set[str], profile_dir: Path = PROFILE_DIR, full: bool = False, stop_after_known: int = 20, headless: bool = False) -> list[Found]`; `sweep_saved(known: set[str], profile_dir: Path = PROFILE_DIR, full: bool = False, username: str | None = None, headless: bool = False) -> list[Found]`.
- `sweep_dm` algorithm: open `url`; if the final URL contains `/accounts/login` raise `LoginRequired`. Loop: evaluate JS that returns `{srcs: [all img src containing "ig_cache_key"], hrefs: [all a href containing "/p/" or "/reel/"], top: <scroller at its start>}` where the scroller is the element with the largest `scrollHeight` whose `scrollHeight > clientHeight`, and `top` is `scrollTop <= -(scrollHeight - clientHeight) + 2` (column-reverse) or `scrollTop <= 2` otherwise; new codes come from `codes_from_srcs(srcs)` plus `codes_from_text(" ".join(hrefs))`, in page order which is newest first; count consecutive codes already in `known` or already collected; stop when `not full and streak >= stop_after_known`, or when `top` has been true for 3 consecutive iterations with no new code; otherwise scroll the scroller by `-450` (column-reverse) or `+450`, wait 700 ms. Source for each code: `{"kind": "dm", "name": <page title before " • " or the thread id from the url>, "via": "live", "ts": now_iso()}`. `headless` exists only for the fixture tests.
- `sweep_saved`: username from the argument, else from the nav profile link on `https://www.instagram.com/` (the `a[href]` whose `img[alt]` ends with `profile picture`), else raise `LoginRequired`. Open `https://www.instagram.com/<username>/saved/all-posts/`, collect `a[href]` codes while scrolling the window by 900 px until 3 rounds add nothing (or streak rule as above); name `saved`. Then open `https://www.instagram.com/<username>/saved/`, read collection links (`a[href*="/saved/"]` other than `all-posts`), and sweep each the same way with the collection's link text as name. Kind `saved`, via `live`.

- [ ] **Step 1: Write the fixtures**

`dm_thread.html`: a `div#list` with `height: 600px; overflow-y: auto; display: flex; flex-direction: column-reverse;` containing 60 child cards each 120 px tall, each with `<img src="https://cdn.example/x.jpg?ig_cache_key=<base64 of "<3700000000000000000 + i>_1">">`, newest (i = 59) first in DOM order, and above them a card `<div class="profile">kungfookah · View profile</div>`. `saved_grid.html`: a body taller than the viewport with 45 `<a href="/p/<media_id_to_shortcode(3800000000000000000 + i)>/">` tiles.

- [ ] **Step 2: Write the failing tests**

```python
import pytest
from pathlib import Path
from unwatched.browser import codes_from_srcs, sweep_dm
from unwatched.shortcode import media_id_to_shortcode

FIX = Path(__file__).parent / "fixtures"
ALL = [media_id_to_shortcode(3700000000000000000 + i) for i in range(59, -1, -1)]

def test_codes_from_srcs_is_pure():
    import base64
    src = "https://cdn/x.jpg?stp=1&ig_cache_key=" + base64.b64encode(b"3700000000000000000_1").decode() + "&_nc=1"
    assert codes_from_srcs([src, src]) == [media_id_to_shortcode(3700000000000000000)]

@pytest.mark.browser
def test_sweep_dm_full_collects_everything(tmp_path):
    found = sweep_dm((FIX / "dm_thread.html").resolve().as_uri(), set(), profile_dir=tmp_path, full=True, headless=True)
    assert [c for c, _, _ in found] == ALL
    assert found[0][1]["kind"] == "dm" and found[0][1]["via"] == "live"

@pytest.mark.browser
def test_sweep_dm_stops_after_known_streak(tmp_path):
    known = set(ALL[5:])
    found = sweep_dm((FIX / "dm_thread.html").resolve().as_uri(), known, profile_dir=tmp_path, headless=True)
    codes = [c for c, _, _ in found]
    assert codes[:5] == ALL[:5] and len(codes) < 40
```

- [ ] **Step 3: Install Chromium and run to verify failure** — `uv run playwright install chromium`; `uv run pytest tests/test_browser.py -v`. Expected: import error.
- [ ] **Step 4: Implement `browser.py` and the CLI wiring.** Keep the JS snippet in one module-level string. `ingest --dm/--saved` passes `known = set(load_posts(work))`.
- [ ] **Step 5: Run to verify pass** — 3 passed. `uv run pytest -m "not browser"` still passes everything else.
- [ ] **Step 6: Commit** — `feat: browser sign-in, DM and saved sweeps, cookie export`

---

### Task 10: Digest through headless Claude

**Files:**
- Create: `src/unwatched/digest.py`, `tests/fake_claude.py`
- Modify: `src/unwatched/cli.py` (add `digest --profile PATH --master PATH [--claude CMD] [--max-turns N]`)
- Test: `tests/test_digest.py`

**Interfaces:**
- Consumes: Task 6 `run_build(new_only=True)`, Task 3 state, Task 13's `skills/unwatched/SKILL.md` (for now a one-line placeholder file with frontmatter is created here and replaced in Task 13).
- Produces: `MARKER = "UNWATCHED_DIGEST_DONE"`; `skill_text() -> str` (reads `unwatched/skill/SKILL.md` from package resources, falling back to `<repo>/skills/unwatched/SKILL.md`); `build_prompt(skill: str, profile: Path, master: Path, input_path: Path) -> str` containing the skill text, then `Mode: headless.`, `Profile: <profile>`, `Master: <master>`, `Input: <input>`, and `When finished print exactly: UNWATCHED_DIGEST_DONE kept=<n> total=<m>`; `parse_marker(stdout: str) -> tuple[int, int] | None`; `run_digest(work: Path, profile: Path, master: Path, claude: str | list[str] = "claude", max_turns: int = 40) -> tuple[bool, str]` that builds `work/digest-input.md` with `new_only=True` (returns `(True, "nothing new")` when zero posts), records the master's mtime (or absence), runs `[*claude, "-p", prompt, "--allowedTools", "Read,Edit,Write,Glob,Grep", "--max-turns", str(max_turns), "--add-dir", str(master.parent), "--add-dir", str(work)]` with `cwd=work`, and succeeds only if exit is 0, `parse_marker` finds the marker, and the master's mtime changed or the file now exists; on success sets `state.last_digest = now_iso()`; the string is the summary or the failure reason with the last 2000 characters of output.

- [ ] **Step 1: Write `tests/fake_claude.py`** — appends `digested\n` to the file named by env `FAKE_MASTER` and prints `UNWATCHED_DIGEST_DONE kept=2 total=5`; with env `FAKE_CLAUDE_SILENT=1` it exits 0 printing nothing and touching nothing.

- [ ] **Step 2: Write the failing tests**

```python
import sys
from pathlib import Path
from unwatched.digest import build_prompt, parse_marker, run_digest
from unwatched.ingest import apply, ingest_export
from unwatched.state import load_state

FAKE = [sys.executable, str(Path(__file__).parent / "fake_claude.py")]
FIX = Path(__file__).parent / "fixtures" / "export"

def test_parse_marker():
    assert parse_marker("blah\nUNWATCHED_DIGEST_DONE kept=3 total=10\n") == (3, 10)
    assert parse_marker("no marker") is None

def test_build_prompt_contains_paths_and_mode(tmp_path):
    p = build_prompt("SKILL", tmp_path / "tech.md", tmp_path / "master.md", tmp_path / "in.md")
    assert p.startswith("SKILL") and "Mode: headless." in p and f"Master: {tmp_path / 'master.md'}" in p and "UNWATCHED_DIGEST_DONE kept=<n> total=<m>" in p

def test_run_digest_success_updates_state(tmp_path, monkeypatch):
    work, master = tmp_path / "work", tmp_path / "master.md"
    apply(work, ingest_export(FIX))
    monkeypatch.setenv("FAKE_MASTER", str(master))
    ok, summary = run_digest(work, tmp_path / "tech.md", master, claude=FAKE)
    assert ok and "kept=2" in summary and master.read_text() == "digested\n"
    assert load_state(work)["last_digest"] is not None

def test_run_digest_fails_without_marker_or_change(tmp_path, monkeypatch):
    work, master = tmp_path / "work", tmp_path / "master.md"
    apply(work, ingest_export(FIX))
    monkeypatch.setenv("FAKE_MASTER", str(master)); monkeypatch.setenv("FAKE_CLAUDE_SILENT", "1")
    ok, summary = run_digest(work, tmp_path / "tech.md", master, claude=FAKE)
    assert not ok and load_state(work)["last_digest"] is None
```

- [ ] **Step 3: Run to verify failure.** — [ ] **Step 4: Implement `digest.py` and the subcommand** (CLI returns `EXIT_DIGEST` on `ok is False`). — [ ] **Step 5: Run to verify pass** — 4 passed. — [ ] **Step 6: Commit** — `feat: daily digest through headless Claude with completion check`

---

### Task 11: Task Scheduler registration

**Files:**
- Create: `src/unwatched/schedule.py`
- Modify: `src/unwatched/cli.py` (add `schedule install [--at HH:MM] [--config PATH] | remove | status`)
- Test: `tests/test_schedule.py`

**Interfaces:**
- Produces: `TASK_NAME = "unwatched daily"`; `build_register_script(exe: str, config: str, at: str) -> str` (PowerShell text: `$a = New-ScheduledTaskAction -Execute '<exe>' -Argument 'run --config "<config>"'`; `$t = New-ScheduledTaskTrigger -Daily -At <at>`; `$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2) -Priority 7`; `$p = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited`; `Register-ScheduledTask -TaskName '<TASK_NAME>' -Action $a -Trigger $t -Settings $s -Principal $p -Force`); `install(at: str, config: Path, exe: Path | None = None) -> None` (exe defaults to the `unwatched` executable next to `sys.executable`'s Scripts dir, or `shutil.which("unwatched")`; runs the script with `powershell -NoProfile -NonInteractive -Command`; raises `NotImplementedError("scheduling is Windows-only in v1; use cron: 0 15 * * * unwatched run --config ...")` on other platforms); `remove() -> None` (`Unregister-ScheduledTask -TaskName '<TASK_NAME>' -Confirm:$false`); `status() -> dict` from `Get-ScheduledTaskInfo -TaskName '<TASK_NAME>' | ConvertTo-Json` with keys `LastRunTime`, `NextRunTime`, `LastTaskResult`.

- [ ] **Step 1: Write the failing tests**

```python
from unwatched.schedule import TASK_NAME, build_register_script

def test_register_script_has_required_settings_and_quotes_spaces():
    s = build_register_script(r"C:\Program Files\unwatched\unwatched.exe", r"C:\Users\me\My Config\unwatched.toml", "15:00")
    assert TASK_NAME == "unwatched daily" and f"-TaskName '{TASK_NAME}'" in s
    assert "-Daily -At 15:00" in s and "-StartWhenAvailable" in s and "-WakeToRun" in s
    assert "-LogonType Interactive" in s and "-Priority 7" in s and "-Hours 2" in s
    assert "-Execute 'C:\\Program Files\\unwatched\\unwatched.exe'" in s
    assert "-Argument 'run --config \"C:\\Users\\me\\My Config\\unwatched.toml\"'" in s
```

- [ ] **Step 2: Run to verify failure.** — [ ] **Step 3: Implement `schedule.py` and the subcommand.** — [ ] **Step 4: Run to verify pass.** — [ ] **Step 5: Commit** — `feat: register the daily Task Scheduler job`

---

### Task 12: The `run` command, logging, and summaries

**Files:**
- Create: `src/unwatched/run.py`
- Modify: `src/unwatched/cli.py` (add `run --config PATH`)
- Test: `tests/test_run.py`

**Interfaces:**
- Consumes: every earlier module.
- Produces: `run_all(cfg: dict, ytdlp: str | list[str] = "yt-dlp", claude: str | list[str] = "claude") -> int` returning an exit code. Order: configure logging to `work/logs/<YYYY-MM-DD>.log` and stderr; `export_cookies` if the profile has a session (skip quietly if `playwright` is not installed or no profile); ingest `cfg["sources"]["export"]`, `["links"]`, each `["dm"]` URL, and `["saved"]`; fetch with `cfg["fetch"]` (cap → return `EXIT_CAP` after writing `state.last_error`); transcribe with `cfg["transcribe"]`; build `work/digest-input.md` with `new_only=True`; digest when `cfg["digest"]` and both `profile` and `master` are set. `LoginRequired` anywhere → `state.last_error = "sign-in expired, run: unwatched login"`, return `EXIT_LOGIN`. On completion set `state.last_run`, `state.last_summary = "ingested <n> new, fetched <f>, failed <x>, transcribed <t>, digest <ok|skipped|failed>"`, clear `last_error` on success.

- [ ] **Step 1: Write the failing test** (no browser, no network: sources are the fixture export and the links file; fetch kinds exclude everything present so nothing is fetched)

```python
import sys
from pathlib import Path
from unwatched.run import run_all
from unwatched.state import load_state

FIX = Path(__file__).parent / "fixtures"

def test_run_all_with_file_sources_only(tmp_path):
    cfg = {"work": str(tmp_path / "w"), "profile": None, "master": None, "digest": False, "username": None,
           "sources": {"dm": [], "saved": False, "links": [str(FIX / "links.md")], "export": [str(FIX / "export")]},
           "fetch": {"kinds": [], "max": 300, "delay": 0}, "transcribe": {"model": "small", "language": "en"}}
    assert run_all(cfg, ytdlp=[sys.executable, str(Path(__file__).parent / "fake_ytdlp.py")]) == 0
    st = load_state(tmp_path / "w")
    assert st["last_run"] and st["last_error"] is None and st["last_summary"].startswith("ingested 6 new, fetched 0")
    assert (tmp_path / "w" / "digest-input.md").exists() and list((tmp_path / "w" / "logs").glob("*.log"))
```

- [ ] **Step 2: Run to verify failure.** — [ ] **Step 3: Implement `run.py` and the subcommand.** — [ ] **Step 4: Run to verify pass.** — [ ] **Step 5: Commit** — `feat: run the whole daily chain with logs and a summary`

---

### Task 13: Skill, plugin manifest, profiles

**Files:**
- Create: `skills/unwatched/SKILL.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `profiles/tech.md`, `profiles/design.md`, `profiles/cooking.md`, `profiles/fashion.md`
- Test: `tests/test_packaging.py`

**Interfaces:**
- `SKILL.md` frontmatter: `name: unwatched`, `description:` one sentence naming the triggers "my saved reels", "Instagram export", "digest my reels", "unwatched". Body: the eight steps and the rules from the spec's skill section, written as instructions to Claude, plus a `## Headless mode` section: when the prompt says `Mode: headless.`, skip steps 1 to 3 and 6, read `Input`, update `Master` in place (Part 1 merge, Part 2 append, Part 3 append with kept/skipped, a `Last updated` line and a dated run entry under `## Changelog`), and finish by printing `UNWATCHED_DIGEST_DONE kept=<n> total=<m>` as the last line. Rules verbatim: never sign in or type credentials; never guess a name correction; never raise the fetch cap without the user; never poll in a loop; always state kept versus total.
- `plugin.json`: `{"name": "unwatched", "version": "0.1.0", "description": <project description>, "author": {"name": "<owner>", "url": "https://github.com/<handle>"}}`. `marketplace.json`: one entry pointing at `./` named `unwatched`. Placeholders replaced in Task 16.
- Profiles: each under 120 words, four labelled paragraphs `Keep:`, `Skip:`, `Extract per post:`, `Output:`. `tech.md` reproduces the prototype's filter (AI tools and agents, Claude Code skills and plugins, GitHub repos, open-source alternatives, developer workflow and DevOps); `design.md` is the spec's example verbatim; `cooking.md` extracts dish, ingredients, steps, source; `fashion.md` is the spec's example verbatim.

- [ ] **Step 1: Write the failing tests**

```python
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_plugin_manifest_and_skill_frontmatter():
    m = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert m["name"] == "unwatched" and m["version"] == "0.1.0"
    skill = (ROOT / "skills" / "unwatched" / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---\nname: unwatched\n") and "UNWATCHED_DIGEST_DONE kept=<n> total=<m>" in skill
    for p in ("tech", "design", "cooking", "fashion"):
        text = (ROOT / "profiles" / f"{p}.md").read_text(encoding="utf-8")
        assert all(k in text for k in ("Keep:", "Skip:", "Extract per post:", "Output:"))
```

- [ ] **Step 2: Run to verify failure.** — [ ] **Step 3: Write the files.** — [ ] **Step 4: Run to verify pass**, then `uv build` and check the wheel contains `unwatched/skill/SKILL.md` (`python -m zipfile -l dist/*.whl`). — [ ] **Step 5: Commit** — `feat: Claude skill, plugin manifest and interest profiles`

---

### Task 14: README and changelog

**Files:**
- Modify: `README.md`, `CHANGELOG.md`

- [ ] **Step 1: Write the README** with these sections in this order: what it does (three sentences); five-minute setup (`uv tool install git+https://github.com/<handle>/unwatched`, `uv tool run --from unwatched playwright install chromium` or the equivalent, `unwatched login`, copy `unwatched.example.toml`, `unwatched ingest --links ... --seen` to seed, `unwatched schedule install`); the commands, one line each; the daily job and what can hold it up (the spec's scheduling list, shortened); profiles and how to write one; Claude Code plugin install (`claude plugin marketplace add <handle>/unwatched`, `claude plugin install unwatched`); backfill from the data export (how to request JSON, which account); privacy (everything local, where the profile lives, nothing sent anywhere but Instagram and, if enabled, your own Claude Code); Instagram terms note (automated collection is against the terms even at this pace; the account is yours to risk); development (CONTRIBUTING pointer).
- [ ] **Step 2: Move the `Unreleased` notes to `## 0.1.0 - <date>` in `CHANGELOG.md`** listing the features by task.
- [ ] **Step 3: Verify** — `uv run pre-commit run --all-files` passes. — [ ] **Step 4: Commit** — `docs: README and 0.1.0 changelog`

---

### Task 15: Smoke run on the owner's machine

This task runs with the owner present. No code changes unless a step fails; a failure is fixed with a test in the owning task's style, then this task resumes.

- [ ] **Step 1: Seed the known posts** — `uv run unwatched ingest --links "C:\Users\<you>\Documents\<research-folder>\all-links.md" --seen --work C:\Users\<you>\unwatched-work`. Expected: `links:all-links.md: 167`, `status` shows `posts: 167` and a `last digest` time.
- [ ] **Step 2: Sign in** — `uv run unwatched login`. A Chromium window opens on Instagram; the owner signs in as the alt account and completes any verification themselves. Expected output: `signed in`.
- [ ] **Step 3: Live sweep** — `uv run unwatched ingest --dm https://www.instagram.com/direct/t/<thread-id>/ --saved --work C:\Users\<you>\unwatched-work`. Expected: `dm:kungfookah: <n>` where n is the number of reels sent since 2026-11-11, saved counts, and `status` posts > 167. If exit 3, repeat Step 2.
- [ ] **Step 4: Fetch and transcribe the new ones** — `uv run unwatched fetch --work ...` then `uv run unwatched transcribe --work ...`. Expected: `fetched <n> failed 0`, transcripts present for the videos. The first transcribe run downloads the small model.
- [ ] **Step 5: Build and digest** — write the owner's config at `C:\Users\<you>\.unwatched\unwatched.toml` (work, `profile = <repo>/profiles/tech.md`, `master = C:\Users\<you>\Documents\<research-folder>\kungfookah-master.md`, `digest = true`, the dm URL, `saved = true`), then `uv run unwatched run --config C:\Users\<you>\.unwatched\unwatched.toml`. Expected: exit 0, the master document gains a `Last updated` line and a changelog entry, `status` shows the summary.
- [ ] **Step 6: Schedule** — `uv run unwatched schedule install --config C:\Users\<you>\.unwatched\unwatched.toml`, then `uv run unwatched schedule status`. Expected: `NextRunTime` is today or tomorrow at 15:00.
- [ ] **Step 7: Record** — add anything learned (DOM changes, timings) to the spec's pitfalls section and commit: `docs: smoke run notes`.

---

### Task 16: Security audit and publish

- [ ] **Step 1: Fill placeholders** — owner name in `LICENSE`, handle in `README.md`, `plugin.json`, `marketplace.json`, `pyproject.toml` `[project.urls]`. Commit `chore: fill owner and repository details`.
- [ ] **Step 2: Security audit** — clone `https://github.com/cloudflare/security-audit-skill` into the scratchpad, read its `SKILL.md`, and run its process against this repo twice (as a subagent each time, report-only). Fix every confirmed finding with a test; commit `fix: <finding>` each.
- [ ] **Step 3: Launch checklist** — run the `open-source-launch` skill from the plugin directory if installed; otherwise check by hand: LICENSE, README install path works from a clean `uv tool install`, no secrets or thread ids in the repo (`git grep -n "direct/t/"` returns only the example file), CI config present.
- [ ] **Step 4: Sign in and create the repo** — owner runs `gh auth login --web` in a terminal; then `gh repo create <handle>/unwatched --public --source . --remote origin --push`.
- [ ] **Step 5: CI green** — `gh run watch` until the first run passes on both OSes. Fix and push if not.
- [ ] **Step 6: Tag and release** — `git tag -a v0.1.0 -m "unwatched 0.1.0"`, `git push --tags`, `gh release create v0.1.0 --notes-from-tag` with the changelog section as notes.
- [ ] **Step 7: Install from GitHub** — on this machine, `uv tool install git+https://github.com/<handle>/unwatched` then `unwatched --help`; re-run `unwatched schedule install` so the task points at the installed executable rather than the dev checkout.

---

## Self-review notes

- Spec coverage: login, DM and saved sweeps (9); export, links, seeding (4); fetch cap, kinds, thread, since, delay, cookies (7, 9); transcribe default and `--only` (8); build `--new-only` (6); digest with marker and mtime check (10); Task Scheduler settings (11); run order, logs, summary, exit codes (12); skill, plugin manifest, profiles (13); README, terms note, privacy (14); engineering practice (1, every task's tests and commits); security audit and launch (16); smoke run with the owner signing in (15). Likes live and carousel OCR are spec non-goals and have no task.
- Review Focus 1 to 5 are pinned in Tasks 4, 4, 4, 7, 11.
- Names used across tasks: `Found`, `apply`, `add_source`, `load_posts`, `new_since`, `now_iso`, `load_state`, `save_state`, `run_build`, `select`, `pending`, `fetch_one`, `run_fetch`, `todo`, `run_transcribe`, `LoginRequired`, `sweep_dm`, `sweep_saved`, `export_cookies`, `run_digest`, `install`, `run_all`, `EXIT_LOGIN`, `EXIT_CAP`, `EXIT_DIGEST`.
