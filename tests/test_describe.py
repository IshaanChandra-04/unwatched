import json
import sys
from pathlib import Path

import pytest

import unwatched.describe as describe_module
from unwatched.describe import PROMPT, ClaudeMissing, describe_one, run_describe
from unwatched.fetch import update_meta

FAKE = [sys.executable, str(Path(__file__).parent / "fake_claude.py")]


def _frames(tmp_path, code, n=2):
    folder = tmp_path / "frames" / code
    folder.mkdir(parents=True)
    for i in range(1, n + 1):
        (folder / f"{i:02d}.jpg").write_bytes(b"jpg")
    return folder


def test_prompt_asks_for_verbatim_text_scenes_and_names():
    assert "frames of one Instagram post" in PROMPT
    assert "verbatim" in PROMPT and "tools, sites, repositories" in PROMPT


def test_run_describe_writes_markdown_next_to_the_frames(tmp_path):
    _frames(tmp_path, "AAAAAAAAAAA")
    assert run_describe(tmp_path, FAKE, None) == {"described": 1, "failed": 0}
    text = (tmp_path / "frames" / "AAAAAAAAAAA.md").read_text(encoding="utf-8")
    assert "Comment SITES" in text
    assert run_describe(tmp_path, FAKE, None) == {"described": 0, "failed": 0}
    assert run_describe(tmp_path, FAKE, {"AAAAAAAAAAA"}) == {"described": 1, "failed": 0}


def test_run_describe_skips_folders_without_pictures(tmp_path):
    (tmp_path / "frames" / "AAAAAAAAAAA").mkdir(parents=True)
    assert run_describe(tmp_path, FAKE, None) == {"described": 0, "failed": 0}


def test_run_describe_counts_failures_and_gives_up_after_three(tmp_path, monkeypatch):
    _frames(tmp_path, "AAAAAAAAAAA")
    monkeypatch.setenv("FAKE_CLAUDE_DESCRIBE_FAIL", "1")
    results = [run_describe(tmp_path, FAKE, None) for _ in range(4)]
    assert results[:3] == [{"described": 0, "failed": 1}] * 3
    assert results[3] == {"described": 0, "failed": 0}
    meta = json.loads((tmp_path / "meta" / "AAAAAAAAAAA.json").read_text(encoding="utf-8"))
    assert meta["describe_retries"] == 3 and "no model" in meta["describe_error"]
    assert not (tmp_path / "frames" / "AAAAAAAAAAA.md").exists()


def test_describe_one_runs_claude_boxed_in_the_frames_folder(tmp_path, monkeypatch):
    folder = _frames(tmp_path, "AAAAAAAAAAA")
    monkeypatch.setenv("FAKE_CLAUDE_ARGV", str(tmp_path / "argv.json"))
    monkeypatch.setenv("FAKE_CLAUDE_CWD", str(tmp_path / "cwd.txt"))
    describe_one(folder, FAKE)
    argv = json.loads((tmp_path / "argv.json").read_text(encoding="utf-8"))
    assert "--restricted" in argv and "--strict-mcp-config" in argv and "-p" in argv
    assert argv[argv.index("--allowedTools") + 1] == "Read,Glob"
    assert Path((tmp_path / "cwd.txt").read_text(encoding="utf-8")).resolve() == folder.resolve()


def test_describe_one_names_a_missing_claude(tmp_path):
    folder = _frames(tmp_path, "AAAAAAAAAAA")
    with pytest.raises(ClaudeMissing, match="claude not found: no-such-claude"):
        describe_one(folder, "no-such-claude")


def test_run_describe_stops_at_a_missing_claude_without_burning_retries(tmp_path):
    _frames(tmp_path, "AAAAAAAAAAA")
    _frames(tmp_path, "BBBBBBBBBBB")
    with pytest.raises(ClaudeMissing):
        run_describe(tmp_path, "no-such-claude", None)
    assert not (tmp_path / "meta").exists()


def test_run_describe_stops_after_three_failures_in_a_row(tmp_path, monkeypatch):
    for code in ("AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC", "DDDDDDDDDDD", "EEEEEEEEEEE"):
        _frames(tmp_path, code)
    monkeypatch.setenv("FAKE_CLAUDE_DESCRIBE_FAIL", "1")
    assert run_describe(tmp_path, FAKE, None) == {"described": 0, "failed": 3}
    assert not (tmp_path / "meta" / "EEEEEEEEEEE.json").exists()


def test_run_describe_caps_the_posts_per_run(tmp_path):
    for code in ("AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC"):
        _frames(tmp_path, code)
    assert run_describe(tmp_path, FAKE, None, max_posts=2) == {"described": 2, "failed": 0}
    assert run_describe(tmp_path, FAKE, None, max_posts=2) == {"described": 1, "failed": 0}


def test_run_describe_waits_for_an_image_posts_slides(tmp_path):
    _frames(tmp_path, "AAAAAAAAAAA", n=1)  # the cover yt-dlp fetched
    update_meta(tmp_path, "AAAAAAAAAAA", media_type="image")
    assert run_describe(tmp_path, FAKE, None) == {"described": 0, "failed": 0}
    update_meta(
        tmp_path, "AAAAAAAAAAA", pictures_retries=3
    )  # the browser gave up: describe the cover
    assert run_describe(tmp_path, FAKE, None) == {"described": 1, "failed": 0}


def test_describe_one_times_out_a_hung_claude(tmp_path, monkeypatch):
    folder = _frames(tmp_path, "AAAAAAAAAAA")
    monkeypatch.setenv("FAKE_CLAUDE_SLEEP", "3")
    monkeypatch.setattr(describe_module, "TIMEOUT_S", 0.3)
    with pytest.raises(RuntimeError, match="timed out"):
        describe_one(folder, FAKE)
