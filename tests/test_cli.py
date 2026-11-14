from pathlib import Path

from unwatched.cli import main

FIX = Path(__file__).parent / "fixtures"


def test_ingest_then_status(tmp_path, capsys):
    rc = main(
        ["ingest", str(FIX / "export"), "--links", str(FIX / "links.md"), "--work", str(tmp_path)]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "dm:kungfookah: 2" in out and "links:links.md: 2" in out
    assert main(["status", "--work", str(tmp_path)]) == 0
    assert "posts: 6" in capsys.readouterr().out


def test_ingest_requires_a_source(tmp_path, capsys):
    assert main(["ingest", "--work", str(tmp_path)]) == 2


def test_fetch_stops_at_cap_before_any_network(tmp_path, capsys):
    main(["ingest", str(FIX / "export"), "--work", str(tmp_path)])
    rc = main(
        ["fetch", "--work", str(tmp_path), "--max", "1", "--ytdlp", "definitely-not-a-program"]
    )
    assert rc == 4
    assert "cap is 1" in capsys.readouterr().out
    assert not (tmp_path / "meta").exists() or not list((tmp_path / "meta").iterdir())
