"""Hand the new posts to headless Claude Code and check that it updated the master document."""

import logging
import re
import subprocess
from importlib import resources
from pathlib import Path

from unwatched.build import run_build
from unwatched.posts import now_iso
from unwatched.state import load_state, save_state

MARKER = "UNWATCHED_DIGEST_DONE"
_MARKER_RE = re.compile(rf"{MARKER} kept=(\d+) total=(\d+)")
log = logging.getLogger("unwatched")


def skill_text() -> str:
    packaged = resources.files("unwatched").joinpath("skill/SKILL.md")
    if packaged.is_file():
        return packaged.read_text(encoding="utf-8")
    repo_copy = Path(__file__).resolve().parents[2] / "skills" / "unwatched" / "SKILL.md"
    return repo_copy.read_text(encoding="utf-8")


def build_prompt(skill: str, profile: Path, master: Path, input_path: Path) -> str:
    return (
        f"{skill}\n\n"
        "Mode: headless.\n"
        f"Profile: {profile}\n"
        f"Master: {master}\n"
        f"Input: {input_path}\n"
        f"When finished print exactly: {MARKER} kept=<n> total=<m>\n"
    )


def parse_marker(stdout: str) -> tuple[int, int] | None:
    m = _MARKER_RE.search(stdout)
    return (int(m.group(1)), int(m.group(2))) if m else None


def run_digest(
    work: Path,
    profile: Path,
    master: Path,
    claude: str | list[str] = "claude",
    max_turns: int = 40,
) -> tuple[bool, str]:
    input_path = work / "digest-input.md"
    if run_build(work, input_path, new_only=True) == 0:
        return True, "nothing new"
    before = master.stat().st_mtime_ns if master.exists() else None
    cmd = [claude] if isinstance(claude, str) else list(claude)
    cmd += [
        "-p",
        build_prompt(skill_text(), profile, master, input_path),
        "--allowedTools",
        "Read,Edit,Write,Glob,Grep",
        "--max-turns",
        str(max_turns),
        "--add-dir",
        str(master.parent),
        "--add-dir",
        str(work),
    ]
    try:
        result = subprocess.run(
            cmd, cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
    except OSError as e:
        return False, f"could not run claude: {e}"
    output = (result.stdout or "") + (result.stderr or "")
    marker = parse_marker(result.stdout or "")
    after = master.stat().st_mtime_ns if master.exists() else None
    if result.returncode != 0 or marker is None or after is None or after == before:
        master_state = "missing" if after is None else "unchanged" if after == before else "ok"
        reason = (
            f"exit {result.returncode}, marker {'found' if marker else 'missing'}, "
            f"master {master_state}"
        )
        log.error("digest failed: %s", reason)
        return False, f"digest failed ({reason}):\n{output[-2000:]}"
    state = load_state(work)
    state["last_digest"] = now_iso()
    save_state(work, state)
    summary = f"digest kept={marker[0]} total={marker[1]}"
    log.info(summary)
    return True, summary
