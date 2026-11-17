"""Hand the new posts to headless Claude Code and check that it updated the master document.

Claude runs inside a fresh temporary folder that holds copies of the digest input, the profile
and the master document, with no other directory and none of the user's MCP servers, so text
written by strangers (captions, transcripts) can at most damage those copies. The edited copy
is copied back only when the run printed the completion marker and changed the file; the
previous version is kept as ``.bak``.
"""

import logging
import re
import shutil
import subprocess
import tempfile
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


def _command(claude: str | list[str]) -> list[str]:
    cmd = [claude] if isinstance(claude, str) else list(claude)
    cmd[0] = shutil.which(cmd[0]) or cmd[0]  # on Windows the CLI is a .CMD shim
    return cmd


def run_digest(
    work: Path,
    profile: Path,
    master: Path,
    claude: str | list[str] = "claude",
    max_turns: int = 40,
) -> tuple[bool, str]:
    if not profile.is_file():
        return False, f"profile not found: {profile}"
    input_path = work / "digest-input.md"
    if run_build(work, input_path, new_only=True) == 0:
        return True, "nothing new"
    with tempfile.TemporaryDirectory(prefix="unwatched-digest-") as tmp:
        box = Path(tmp)
        shutil.copy(input_path, box / "digest-input.md")
        shutil.copy(profile, box / "profile.md")
        box_master = box / master.name
        if master.exists():
            shutil.copy(master, box_master)
        before = box_master.stat().st_mtime_ns if box_master.exists() else None
        prompt = build_prompt(skill_text(), box / "profile.md", box_master, box / "digest-input.md")
        cmd = _command(claude) + [
            "-p",
            "--restricted",
            "--strict-mcp-config",
            "--allowedTools",
            "Read,Edit,Write,Glob,Grep",
            "--max-turns",
            str(max_turns),
        ]
        try:
            # the prompt goes on stdin: it starts with "---" and spans lines, which argv mangles
            result = subprocess.run(
                cmd,
                cwd=box,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError:
            hint = 'install Claude Code or set claude = "<path to it>" in unwatched.toml'
            return False, f"claude not found: {cmd[0]}; {hint}"
        except OSError as e:
            return False, f"could not run claude: {e}"
        output = (result.stdout or "") + (result.stderr or "")
        marker = parse_marker(result.stdout or "")
        after = box_master.stat().st_mtime_ns if box_master.exists() else None
        if result.returncode != 0 or marker is None or after is None or after == before:
            master_state = "missing" if after is None else "unchanged" if after == before else "ok"
            reason = (
                f"exit {result.returncode}, marker {'found' if marker else 'missing'}, "
                f"master {master_state}"
            )
            log.error("digest failed: %s", reason)
            return False, f"digest failed ({reason}):\n{output[-2000:]}"
        master.parent.mkdir(parents=True, exist_ok=True)
        if master.exists():
            shutil.copy(master, master.with_name(master.name + ".bak"))
        shutil.copy(box_master, master)
    state = load_state(work)
    state["last_digest"] = now_iso()
    save_state(work, state)
    summary = f"digest kept={marker[0]} total={marker[1]}"
    log.info(summary)
    return True, summary
