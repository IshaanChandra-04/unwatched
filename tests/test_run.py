import sys
from pathlib import Path

from unwatched.run import run_all
from unwatched.state import load_state

FIX = Path(__file__).parent / "fixtures"
FAKE_YTDLP = [sys.executable, str(FIX.parent / "fake_ytdlp.py")]


def test_run_all_with_file_sources_only(tmp_path):
    cfg = {
        "work": str(tmp_path / "w"),
        "profile": None,
        "master": None,
        "digest": False,
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
    assert run_all(cfg, ytdlp=FAKE_YTDLP) == 0
    state = load_state(tmp_path / "w")
    assert state["last_run"] and state["last_error"] is None
    assert state["last_summary"].startswith("ingested 6 new, fetched 0")
    assert (tmp_path / "w" / "digest-input.md").exists()
    assert list((tmp_path / "w" / "logs").glob("*.log"))
