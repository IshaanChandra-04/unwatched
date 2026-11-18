"""Register the daily job: Task Scheduler on Windows, launchd on macOS, cron on Linux."""

import json
import os
import platform
import plistlib
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

TASK_NAME = "unwatched daily"
LABEL = "com.unwatched.daily"
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
CRON_TAG = "# unwatched daily"


def build_register_script(exe: str, config: str, at: str) -> str:
    exe, config = exe.replace("'", "''"), config.replace("'", "''")
    return "\n".join(
        [
            f"$a = New-ScheduledTaskAction -Execute '{exe}' -Argument 'run --config \"{config}\"'",
            f"$t = New-ScheduledTaskTrigger -Daily -At '{at}'",
            "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun "
            "-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
            "-ExecutionTimeLimit (New-TimeSpan -Hours 2) -Priority 7",
            "$p = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive "
            "-RunLevel Limited",
            f"Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $a -Trigger $t "
            "-Settings $s -Principal $p -Force | Out-Null",
        ]
    )


def build_launchd_plist(exe: str, config: str, at: str) -> str:
    """A launchd agent: runs at the time each day, and at wake when the time was slept through."""
    hour, minute = (int(x) for x in at.split(":"))
    log = str(Path.home() / ".unwatched" / "launchd.log")
    agent = {
        "Label": LABEL,
        "ProgramArguments": [exe, "run", "--config", config],
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "StandardOutPath": log,
        "StandardErrorPath": log,
    }
    return plistlib.dumps(agent, sort_keys=False).decode("utf-8")


def build_cron_line(exe: str, config: str, at: str) -> str:
    """cron runs with a bare PATH and no display; the line carries both."""
    hour, minute = (int(x) for x in at.split(":"))
    command = f"DISPLAY=:0 {shlex.quote(exe)} run --config {shlex.quote(config)}"
    return f"{minute} {hour} * * * {command} {CRON_TAG}"


def _run(cmd: list[str], input: str | None = None) -> str:
    result = subprocess.run(
        cmd, input=input, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"{cmd[0]} exited {result.returncode}")
    return result.stdout


def _powershell(script: str) -> str:
    return _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script])


def _crontab() -> list[str]:
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return result.stdout.splitlines() if result.returncode == 0 else []  # "no crontab" exits 1


def _domain() -> str:
    return f"gui/{os.getuid()}"


def default_exe() -> str:
    found = shutil.which("unwatched")
    return found or str(Path(sys.executable).with_name("unwatched.exe"))


def install(at: str, config: Path, exe: Path | None = None) -> None:
    exe_s, config_s = str(exe or default_exe()), str(config.resolve())
    system = platform.system()
    if system == "Windows":
        _powershell(build_register_script(exe_s, config_s, at))
    elif system == "Darwin":
        PLIST.parent.mkdir(parents=True, exist_ok=True)
        PLIST.write_text(build_launchd_plist(exe_s, config_s, at), encoding="utf-8")
        subprocess.run(["launchctl", "bootout", _domain(), str(PLIST)], capture_output=True)
        _run(["launchctl", "bootstrap", _domain(), str(PLIST)])
    else:
        lines = [line for line in _crontab() if not line.endswith(CRON_TAG)]
        lines.append(build_cron_line(exe_s, config_s, at))
        _run(["crontab", "-"], input="\n".join(lines) + "\n")


def remove() -> None:
    system = platform.system()
    if system == "Windows":
        _powershell(f"Unregister-ScheduledTask -TaskName '{TASK_NAME}' -Confirm:$false")
    elif system == "Darwin":
        subprocess.run(["launchctl", "bootout", _domain(), str(PLIST)], capture_output=True)
        PLIST.unlink(missing_ok=True)
    else:
        lines = [line for line in _crontab() if not line.endswith(CRON_TAG)]
        _run(["crontab", "-"], input="\n".join(lines) + "\n")


def status() -> dict:
    system = platform.system()
    if system == "Windows":
        out = _powershell(
            f"$i = Get-ScheduledTaskInfo -TaskName '{TASK_NAME}'; "
            "@{LastRunTime=$i.LastRunTime.ToString('yyyy-MM-dd HH:mm'); "
            "NextRunTime=$i.NextRunTime.ToString('yyyy-MM-dd HH:mm'); "
            "LastTaskResult=$i.LastTaskResult} | ConvertTo-Json"
        )
        return json.loads(out)
    if system == "Darwin":
        return {"installed": PLIST.exists(), "where": str(PLIST)}
    line = next((line for line in _crontab() if line.endswith(CRON_TAG)), None)
    return {"installed": line is not None, "where": line or "crontab"}
