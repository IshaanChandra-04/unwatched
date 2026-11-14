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
    assert p.startswith("SKILL")
    assert "Mode: headless." in p
    assert f"Master: {tmp_path / 'master.md'}" in p
    assert "UNWATCHED_DIGEST_DONE kept=<n> total=<m>" in p


def test_run_digest_success_copies_back_and_keeps_a_backup(tmp_path):
    work, master = tmp_path / "work", tmp_path / "docs" / "master.md"
    master.parent.mkdir()
    master.write_text("old\n", encoding="utf-8")
    apply(work, ingest_export(FIX))
    ok, summary = run_digest(work, tmp_path / "tech.md", master, claude=FAKE)
    assert ok and "kept=2" in summary
    assert master.read_text(encoding="utf-8") == "old\ndigested\n"
    assert (tmp_path / "docs" / "master.md.bak").read_text(encoding="utf-8") == "old\n"
    assert load_state(work)["last_digest"] is not None


def test_run_digest_creates_a_missing_master(tmp_path):
    work, master = tmp_path / "work", tmp_path / "master.md"
    apply(work, ingest_export(FIX))
    ok, _ = run_digest(work, tmp_path / "tech.md", master, claude=FAKE)
    assert ok and master.read_text(encoding="utf-8") == "digested\n"


def test_run_digest_fails_without_marker_or_change(tmp_path, monkeypatch):
    work, master = tmp_path / "work", tmp_path / "master.md"
    master.write_text("old\n", encoding="utf-8")
    apply(work, ingest_export(FIX))
    monkeypatch.setenv("FAKE_CLAUDE_SILENT", "1")
    ok, summary = run_digest(work, tmp_path / "tech.md", master, claude=FAKE)
    assert not ok
    assert master.read_text(encoding="utf-8") == "old\n"
    assert load_state(work)["last_digest"] is None
