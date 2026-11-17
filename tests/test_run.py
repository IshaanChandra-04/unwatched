import logging
import sys
from pathlib import Path

from unwatched.posts import load_posts
from unwatched.run import run_all
from unwatched.state import load_state

FIX = Path(__file__).parent / "fixtures"
FAKE_YTDLP = [sys.executable, str(FIX.parent / "fake_ytdlp.py")]


def _cfg(tmp_path, **over):
    cfg = {
        "work": str(tmp_path / "w"),
        "profile": None,
        "master": None,
        "digest": False,
        "digest_max_turns": 60,
        "claude": "claude",
        "username": None,
        "sources": {
            "dm": [],
            "saved": False,
            "links": [str(FIX / "links.md")],
            "export": [str(FIX / "export")],
        },
        "fetch": {"kinds": [], "max": 300, "delay": 0},
        "transcribe": {"model": "small", "language": "en"},
    }
    cfg.update(over)
    return cfg


def test_run_all_records_a_crash_instead_of_raising(tmp_path):
    cfg = _cfg(tmp_path, sources={"dm": [], "saved": False, "links": [], "export": ["missing.zip"]})
    assert run_all(cfg, ytdlp=FAKE_YTDLP) == 1
    state = load_state(tmp_path / "w")
    assert state["last_run"] and state["last_summary"] == "run crashed"
    assert "missing.zip" in state["last_error"]


def test_run_all_flags_a_run_where_every_fetch_failed(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_YTDLP_FAIL", "1")
    cfg = _cfg(tmp_path, fetch={"kinds": ["saved", "dm"], "max": 300, "delay": 0})
    assert run_all(cfg, ytdlp=FAKE_YTDLP) == 0
    state = load_state(tmp_path / "w")
    assert state["last_error"] and "every fetch failed" in state["last_error"]


def test_run_all_with_file_sources_only(tmp_path):
    cfg = _cfg(tmp_path)
    assert run_all(cfg, ytdlp=FAKE_YTDLP) == 0
    state = load_state(tmp_path / "w")
    assert state["last_run"] and state["last_error"] is None
    assert state["last_summary"].startswith("ingested 6 new, fetched 0")
    assert (tmp_path / "w" / "digest-input.md").exists()
    assert list((tmp_path / "w" / "logs").glob("*.log"))


def test_run_log_quiets_the_transcription_libraries(tmp_path):
    run_all(_cfg(tmp_path), ytdlp=FAKE_YTDLP)
    logging.getLogger("faster_whisper").info("Processing audio with duration 00:42")
    logging.getLogger("huggingface_hub").info("Fetching 5 files")
    text = next((tmp_path / "w" / "logs").glob("*.log")).read_text(encoding="utf-8")
    assert "Processing audio" not in text and "Fetching 5 files" not in text


def test_run_all_keeps_dm_posts_when_the_saved_sweep_fails(tmp_path, monkeypatch):
    import unwatched.browser as browser

    dm_post = (
        "DQ6yR4LMvxY",
        {"kind": "dm", "name": "t", "via": "live", "ts": "2026-11-16T00:00:00Z"},
        None,
    )
    monkeypatch.setattr(browser, "export_cookies", lambda: None)
    monkeypatch.setattr(browser, "sweep_dm", lambda url, known: [dm_post])

    def slow_page(known, username=None):
        raise TimeoutError("Page.goto: Timeout 30000ms exceeded")

    monkeypatch.setattr(browser, "sweep_saved", slow_page)
    live = {
        "dm": ["https://www.instagram.com/direct/t/1/"],
        "saved": True,
        "links": [],
        "export": [],
    }
    assert run_all(_cfg(tmp_path, sources=live), ytdlp=FAKE_YTDLP) == 0
    assert "DQ6yR4LMvxY" in load_posts(tmp_path / "w")
    state = load_state(tmp_path / "w")
    assert state["last_summary"].startswith("ingested 1 new")
    assert "saved sweep failed" in state["last_error"] and "Timeout" in state["last_error"]


def test_run_all_passes_the_configured_claude_to_the_digest(tmp_path, monkeypatch):
    seen = {}

    def fake_digest(work, profile, master, claude, max_turns):
        seen["claude"] = claude
        return True, "digest kept=0 total=0"

    monkeypatch.setattr("unwatched.run.run_digest", fake_digest)
    cfg = _cfg(tmp_path, digest=True, profile="p.md", master="m.md", claude="C:/tools/claude.exe")
    assert run_all(cfg, ytdlp=FAKE_YTDLP) == 0
    assert seen["claude"] == "C:/tools/claude.exe"
