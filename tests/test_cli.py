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
