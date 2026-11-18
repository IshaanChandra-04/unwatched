"""Check the machine for everything unwatched needs, and say how to fix what is missing."""

import shutil
import sys
from importlib import metadata
from pathlib import Path

from unwatched.fetch import COOKIES_PATH

Check = tuple[str, bool, str]  # name, ok, detail or fix
_DISTS = ("yt-dlp", "faster-whisper", "av", "pillow", "playwright")


def _version(dist: str) -> str | None:
    try:
        return metadata.version(dist)
    except metadata.PackageNotFoundError:
        return None


def _browser_check() -> Check:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            path = Path(p.chromium.executable_path)
    except Exception as e:  # Playwright itself is broken, not just the browser
        return ("browser", False, f"Playwright could not start: {e}")
    if path.exists():
        return ("browser", True, f"Chromium at {path}")
    return ("browser", False, "Chromium is not installed; run: unwatched login (it installs it)")


def checks(cfg: dict | None) -> list[Check]:
    """Every check, in the order a first run meets them; the config section only with a config."""
    v = sys.version_info
    out: list[Check] = [
        (
            "python",
            v >= (3, 11),
            f"{v.major}.{v.minor}.{v.micro}" + ("" if v >= (3, 11) else "; needs 3.11 or newer"),
        )
    ]
    for dist in _DISTS:
        ver = _version(dist)
        out.append((dist, ver is not None, ver or "not installed; reinstall unwatched"))
    out.append(_browser_check())
    signed = COOKIES_PATH.exists() and "sessionid" in COOKIES_PATH.read_text(
        encoding="utf-8", errors="replace"
    )
    out.append(
        ("sign-in", signed, f"cookies in {COOKIES_PATH}" if signed else "run: unwatched login")
    )
    if cfg is None:
        return out
    if cfg["digest"]:
        found = shutil.which(cfg["claude"])
        hint = (
            f"{cfg['claude']} not found; install Claude Code "
            'or set claude = "<full path>" in unwatched.toml'
        )
        out.append(("claude", found is not None, found or hint))
        profile, master = cfg["profile"], cfg["master"]
        out.append(
            (
                "profile",
                bool(profile) and Path(profile).is_file(),
                profile
                or 'digest = true needs profile = "tech" (or another profile) in unwatched.toml',
            )
        )
        out.append(
            (
                "master",
                bool(master) and Path(master).parent.is_dir(),
                master or "digest = true needs master = <path of the document to keep>",
            )
        )
    work = Path(cfg["work"])
    try:
        work.mkdir(parents=True, exist_ok=True)
        ok = True
    except OSError:
        ok = False
    out.append(("work", ok, str(work) if ok else f"cannot create {work}"))
    return out
