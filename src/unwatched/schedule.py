"""Register the daily job with Windows Task Scheduler."""

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

TASK_NAME = "unwatched daily"


def build_register_script(exe: str, config: str, at: str) -> str:
    # shortcut: paths are wrapped in PowerShell single quotes, so a path containing a quote
    # character breaks registration; escape it if that ever happens
    return "\n".join(
        [
            f"$a = New-ScheduledTaskAction -Execute '{exe}' -Argument 'run --config \"{config}\"'",
            f"$t = New-ScheduledTaskTrigger -Daily -At {at}",
            "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun "
            "-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
            "-ExecutionTimeLimit (New-TimeSpan -Hours 2) -Priority 7",
            "$p = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive "
            "-RunLevel Limited",
            f"Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $a -Trigger $t "
            "-Settings $s -Principal $p -Force | Out-Null",
        ]
    )


def _powershell(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"powershell exited {result.returncode}")
    return result.stdout


def default_exe() -> str:
    found = shutil.which("unwatched")
    return found or str(Path(sys.executable).with_name("unwatched.exe"))


def install(at: str, config: Path, exe: Path | None = None) -> None:
    if platform.system() != "Windows":
        raise NotImplementedError(
            "scheduling is Windows-only in v1; use cron: "
            f"0 15 * * * unwatched run --config {config}"
        )
    _powershell(build_register_script(str(exe or default_exe()), str(config.resolve()), at))


def remove() -> None:
    _powershell(f"Unregister-ScheduledTask -TaskName '{TASK_NAME}' -Confirm:$false")


def status() -> dict:
    out = _powershell(
        f"$i = Get-ScheduledTaskInfo -TaskName '{TASK_NAME}'; "
        "@{LastRunTime=$i.LastRunTime.ToString('yyyy-MM-dd HH:mm'); "
        "NextRunTime=$i.NextRunTime.ToString('yyyy-MM-dd HH:mm'); "
        "LastTaskResult=$i.LastTaskResult} | ConvertTo-Json"
    )
    return json.loads(out)
