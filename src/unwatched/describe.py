"""Turn a post's pictures into text: headless Claude reads the frames and writes what is on screen.

Claude runs inside the post's own frames folder, with Read and Glob only and none of the user's
MCP servers, so the pictures are all it can see and all it can touch is nothing.
"""

import logging
import subprocess
from pathlib import Path

from unwatched.digest import _command
from unwatched.fetch import pictures, read_meta, update_meta

PROMPT = """\
The image files in the current folder are frames of one Instagram post (a reel or the slides of
a carousel), in time order when sorted by file name. Read every one of them with the Read tool,
then write a markdown report with exactly these three sections:

## Text on screen
Every piece of visible text, verbatim, in the order it appears: titles, captions, numbered or
bulleted lists, code, commands, URLs, usernames and handles, product, site and repository names,
prices, button labels. Keep the original wording and spelling. Group text that belongs to the
same frame under a line naming the frame file.

## What is shown
One line per distinct scene: what the frame shows (a person talking, a phone screen, a terminal,
a website, a code editor, slides, a product) and anything that identifies the app or site.

## Names
The tools, sites, repositories, people and companies that appear, one per line, with the frame
they appear in.

Quote, do not summarise, interpret or advise. If a frame holds no text, say "no text" for it.
Do not run anything and do not write files; your reply is the report.
"""
_MAX_TRIES = 3
log = logging.getLogger("unwatched")


def describe_one(frames_dir: Path, claude: str | list[str], max_turns: int = 30) -> str:
    """Run headless Claude in ``frames_dir`` and return its report; raise RuntimeError otherwise."""
    cmd = _command(claude) + [
        "-p",
        "--restricted",
        "--strict-mcp-config",
        "--allowedTools",
        "Read,Glob",
        "--max-turns",
        str(max_turns),
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=frames_dir,
            input=PROMPT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        hint = 'install Claude Code or set claude = "<path to it>" in unwatched.toml'
        raise RuntimeError(f"claude not found: {cmd[0]}; {hint}") from None
    text = (result.stdout or "").strip()
    if result.returncode != 0 or not text:
        tail = ((result.stderr or "") + (result.stdout or "")).strip()[-500:]
        raise RuntimeError(f"claude exited {result.returncode}: {tail or 'no output'}")
    return text


def todo(work: Path, only: set[str] | None) -> list[str]:
    """Posts with pictures and no report yet, skipping those that failed three times."""
    root = work / "frames"
    if not root.is_dir():
        return []
    codes = (
        sorted(only) if only is not None else sorted(p.name for p in root.iterdir() if p.is_dir())
    )
    out = []
    for code in codes:
        if not pictures(work, code):
            continue
        if only is None and (root / f"{code}.md").exists():
            continue
        if only is None and read_meta(work, code).get("describe_retries", 0) >= _MAX_TRIES:
            continue
        out.append(code)
    return out


def run_describe(work: Path, claude: str | list[str], only: set[str] | None) -> dict[str, int]:
    counts = {"described": 0, "failed": 0}
    for code in todo(work, only):
        folder = work / "frames" / code
        try:
            text = describe_one(folder, claude)
        except RuntimeError as e:
            tries = read_meta(work, code).get("describe_retries", 0) + 1
            update_meta(work, code, describe_error=str(e)[-500:], describe_retries=tries)
            counts["failed"] += 1
            log.warning("describe %s failed: %s", code, str(e).splitlines()[0])
            continue
        (work / "frames" / f"{code}.md").write_text(text + "\n", encoding="utf-8")
        update_meta(work, code, describe_error=None)
        counts["described"] += 1
        log.info("described %s (%d chars)", code, len(text))
    return counts
