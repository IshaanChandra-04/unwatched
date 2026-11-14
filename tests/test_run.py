import sys
from pathlib import Path

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
