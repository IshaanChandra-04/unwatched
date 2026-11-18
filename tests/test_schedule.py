import subprocess
from pathlib import Path

from unwatched import schedule
from unwatched.schedule import (
    TASK_NAME,
    build_cron_line,
    build_launchd_plist,
    build_register_script,
)


def test_register_script_has_required_settings_and_quotes_spaces():
    s = build_register_script(
        r"C:\Program Files\unwatched\unwatched.exe",
        r"C:\Users\me\My Config\unwatched.toml",
        "15:00",
    )
    assert TASK_NAME == "unwatched daily"
    assert f"-TaskName '{TASK_NAME}'" in s
    assert "-Daily -At '15:00'" in s
    assert "-StartWhenAvailable" in s and "-WakeToRun" in s
    assert "-LogonType Interactive" in s and "-Priority 7" in s and "-Hours 2" in s
    assert "-Execute 'C:\\Program Files\\unwatched\\unwatched.exe'" in s
    assert "-Argument 'run --config \"C:\\Users\\me\\My Config\\unwatched.toml\"'" in s


def test_register_script_escapes_single_quotes_in_paths():
    s = build_register_script(
        r"C:\Users\O'Brien\unwatched.exe", r"C:\Users\O'Brien\u.toml", "09:30"
    )
    assert "-Execute 'C:\\Users\\O''Brien\\unwatched.exe'" in s
    assert "-Argument 'run --config \"C:\\Users\\O''Brien\\u.toml\"'" in s


def test_launchd_plist_runs_the_job_daily_at_the_time():
    s = build_launchd_plist("/opt/bin/unwatched", "/Users/me/u.toml", "15:00")
    assert "<string>com.unwatched.daily</string>" in s
    assert "<integer>15</integer>" in s and "<integer>0</integer>" in s
    assert "<string>/opt/bin/unwatched</string>" in s and "<string>/Users/me/u.toml</string>" in s
    assert "StartCalendarInterval" in s and "launchd.log" in s


def test_cron_line_quotes_paths_and_sets_the_display():
    line = build_cron_line("/usr/local/bin/unwatched", "/home/me/My Config/u.toml", "09:30")
    assert line == (
        "30 9 * * * DISPLAY=:0 /usr/local/bin/unwatched run --config "
        "'/home/me/My Config/u.toml' # unwatched daily"
    )


def test_install_on_linux_keeps_the_users_other_cron_lines(monkeypatch, tmp_path):
    monkeypatch.setattr(schedule.platform, "system", lambda: "Linux")
    written = {}

    def fake_run(cmd, **kwargs):
        if cmd == ["crontab", "-l"]:
            old = "0 1 * * * backup\n5 5 * * * old # unwatched daily\n"
            return subprocess.CompletedProcess(cmd, 0, stdout=old, stderr="")
        if cmd == ["crontab", "-"]:
            written["text"] = kwargs["input"]
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        raise AssertionError(cmd)

    monkeypatch.setattr(schedule.subprocess, "run", fake_run)
    schedule.install("15:00", tmp_path / "u.toml", exe=Path("/usr/local/bin/unwatched"))
    lines = written["text"].splitlines()
    assert lines[0] == "0 1 * * * backup" and len(lines) == 2
    assert lines[1].startswith("0 15 * * * DISPLAY=:0") and not lines[1].startswith("5 5")


def test_status_and_remove_use_launchd_on_macos(monkeypatch, tmp_path):
    monkeypatch.setattr(schedule.platform, "system", lambda: "Darwin")
    plist = tmp_path / "com.unwatched.daily.plist"
    monkeypatch.setattr(schedule, "PLIST", plist)
    monkeypatch.setattr(schedule, "_domain", lambda: "gui/501")
    assert schedule.status() == {"installed": False, "where": str(plist)}
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(schedule.subprocess, "run", fake_run)
    plist.write_text("x", encoding="utf-8")
    assert schedule.status()["installed"] is True
    schedule.remove()
    assert not plist.exists() and calls[0][:2] == ["launchctl", "bootout"]
