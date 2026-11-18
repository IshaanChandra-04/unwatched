from unwatched import doctor
from unwatched.cli import main


def _by_name(checks):
    return {name: (ok, detail) for name, ok, detail in checks}


def test_checks_report_a_missing_claude_only_when_the_digest_is_on(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    monkeypatch.setattr(doctor, "_browser_check", lambda: ("browser", True, "stub"))
    cfg = {
        "digest": True,
        "claude": "claude",
        "profile": None,
        "master": None,
        "work": str(tmp_path / "w"),
    }
    found = _by_name(doctor.checks(cfg))
    assert found["claude"][0] is False and "unwatched.toml" in found["claude"][1]
    assert found["profile"][0] is False and found["master"][0] is False
    assert found["work"][0] is True
    cfg["digest"] = False
    assert "claude" not in _by_name(doctor.checks(cfg))


def test_checks_pass_for_an_installed_tool(monkeypatch):
    monkeypatch.setattr(doctor, "_browser_check", lambda: ("browser", True, "stub"))
    found = _by_name(doctor.checks(None))
    assert found["python"][0] and found["yt-dlp"][0] and found["pillow"][0]
    assert "sign-in" in found


def test_doctor_exit_code_follows_the_checks(monkeypatch, capsys):
    monkeypatch.setattr(doctor, "checks", lambda cfg: [("x", False, "fix me"), ("y", True, "fine")])
    assert main(["doctor"]) == 1
    out = capsys.readouterr().out
    assert "fix  x: fix me" in out and "ok   y: fine" in out
    monkeypatch.setattr(doctor, "checks", lambda cfg: [("y", True, "fine")])
    assert main(["doctor"]) == 0
