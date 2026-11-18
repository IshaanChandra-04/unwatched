from pathlib import Path

import pytest

from unwatched import schedule
from unwatched.cli import main

FIX = Path(__file__).parent / "fixtures"


def test_ingest_then_status(tmp_path, capsys):
    rc = main(
        ["ingest", str(FIX / "export"), "--links", str(FIX / "links.md"), "--work", str(tmp_path)]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "dm:alt_account: 2" in out and "links:links.md: 2" in out
    assert main(["status", "--work", str(tmp_path)]) == 0
    assert "posts: 6" in capsys.readouterr().out


def test_ingest_requires_a_source(tmp_path, capsys):
    assert main(["ingest", "--work", str(tmp_path)]) == 2


def test_fetch_only_bypasses_the_seen_marker(tmp_path, monkeypatch):
    import json
    import sys

    fake = [sys.executable, str(Path(__file__).parent / "fake_ytdlp.py")]
    monkeypatch.setenv("FAKE_YTDLP_JSON", json.dumps({"uploader": "u", "duration": 5}))
    main(["ingest", "--links", str(FIX / "links.md"), "--seen", "--work", str(tmp_path)])
    rc = main(["fetch", "--work", str(tmp_path), "--only", "EEEEEEEEEEE", "--ytdlp", *fake])
    assert rc == 0
    meta = json.loads((tmp_path / "meta" / "EEEEEEEEEEE.json").read_text(encoding="utf-8"))
    assert meta["uploader"] == "u"


def test_schedule_install_rejects_a_bad_time(tmp_path, capsys):
    rc = main(["schedule", "install", "--at", "3pm", "--config", str(tmp_path / "u.toml")])
    assert rc == 2
    assert "HH:MM" in capsys.readouterr().err


def test_fetch_stops_at_cap_before_any_network(tmp_path, capsys):
    main(["ingest", str(FIX / "export"), "--work", str(tmp_path)])
    rc = main(
        ["fetch", "--work", str(tmp_path), "--max", "1", "--ytdlp", "definitely-not-a-program"]
    )
    assert rc == 4
    assert "cap is 1" in capsys.readouterr().out
    assert not (tmp_path / "meta").exists() or not list((tmp_path / "meta").iterdir())


def test_fetch_kinds_tolerates_spaces(tmp_path, capsys):
    main(["ingest", str(FIX / "export"), "--work", str(tmp_path)])
    rc = main(
        ["fetch", "--work", str(tmp_path), "--kinds", "dm ", "--max", "1", "--ytdlp", "no-program"]
    )
    assert rc == 4
    assert "cap is 1" in capsys.readouterr().out


def test_schedule_install_refuses_an_unreadable_config(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(schedule, "install", lambda *a, **k: pytest.fail("install was called"))
    assert main(["schedule", "install", "--config", str(tmp_path / "missing.toml")]) == 2
    bad = tmp_path / "bad.toml"
    bad.write_text("work = [unclosed\n", encoding="utf-8")
    assert main(["schedule", "install", "--config", str(bad)]) == 2
    assert "bad.toml" in capsys.readouterr().err


def test_frames_describe_and_pictures_run_on_an_empty_work_dir(tmp_path, capsys):
    assert main(["frames", "--work", str(tmp_path)]) == 0
    assert "sampled 0" in capsys.readouterr().out
    assert main(["describe", "--work", str(tmp_path), "--claude", "no-such-claude"]) == 0
    assert "described 0" in capsys.readouterr().out
    assert main(["pictures", "--work", str(tmp_path)]) == 0
    assert "nothing to fetch" in capsys.readouterr().out


def test_digest_accepts_max_posts():
    from unwatched.cli import _parser

    args = _parser().parse_args(["digest", "--profile", "p", "--master", "m", "--max-posts", "2"])
    assert args.max_posts == 2


def test_main_returns_130_on_ctrl_c(monkeypatch):
    import unwatched.cli as cli

    def interrupted(args):
        raise KeyboardInterrupt

    monkeypatch.setitem(cli._COMMANDS, "status", interrupted)
    assert main(["status"]) == 130


def test_run_prints_a_config_error_instead_of_a_traceback(tmp_path, capsys):
    (tmp_path / "u.toml").write_text("digest_max_turn = 1\n", encoding="utf-8")
    assert main(["run", "--config", str(tmp_path / "u.toml")]) == 2
    assert "digest_max_turn" in capsys.readouterr().err
