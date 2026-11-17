"""Fetch metadata and audio for posts with yt-dlp, one post at a time."""

import json
import logging
import subprocess
import sys
import time
from pathlib import Path

from unwatched.posts import load_posts

COOKIES_PATH = Path.home() / ".unwatched" / "cookies.txt"
# the module in this interpreter, not a PATH lookup: `uv tool install` exposes no yt-dlp binary
DEFAULT_YTDLP = [sys.executable, "-m", "yt_dlp"]
log = logging.getLogger("unwatched")


def select(
    posts: dict[str, dict],
    kinds: set[str],
    threads: set[str] | None,
    since: str | None,
    only: set[str] | None,
) -> list[str]:
    def wanted(rec: dict) -> bool:
        if only is not None:
            return rec["code"] in only
        if since and rec["first_seen"] <= since:
            return False
        return any(
            s["kind"] in kinds and (s["kind"] != "dm" or threads is None or s["name"] in threads)
            for s in rec["sources"]
        )

    codes = [c for c, r in posts.items() if wanted(r)]
    return sorted(codes, key=lambda c: posts[c]["first_seen"])


def pending(work: Path, codes: list[str]) -> list[str]:
    """Codes not fetched yet, plus codes whose fetch has failed fewer than three times."""
    out = []
    for code in codes:
        path = work / "meta" / f"{code}.json"
        meta = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        if meta is None or (meta.get("error") and meta.get("retries", 0) < 3):
            out.append(code)
    return out


def trim_meta(code: str, info: dict) -> dict:
    if info.get("_type") == "playlist":
        durations = [e.get("duration") for e in info.get("entries", []) if e.get("duration")]
        duration = max(durations) if durations else None
    else:
        duration = info.get("duration") or None
    return {
        "code": code,
        "uploader": info.get("uploader"),
        "caption": info.get("description"),
        "upload_date": info.get("upload_date"),
        "duration": duration,
        "media_type": "video" if duration else "image",
        "error": None,
    }


def _run(ytdlp: str | list[str], *args: str) -> subprocess.CompletedProcess:
    cmd = ([ytdlp] if isinstance(ytdlp, str) else list(ytdlp)) + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"yt-dlp exited {result.returncode}")
    return result


def fetch_one(
    code: str,
    url: str | None,
    work: Path,
    cookies: Path | None,
    ytdlp: str | list[str] = DEFAULT_YTDLP,
) -> dict:
    """Write ``meta/<code>.json`` and, for videos, ``audio/<code>.m4a``. Never raises."""
    path = work / "meta" / f"{code}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if url is None:  # archived post shipped inside the export
        meta = trim_meta(code, {"duration": 1}) | {"local": True, "duration": None}
    else:
        cookie_args = ["--cookies", str(cookies)] if cookies else []
        meta = trim_meta(code, {}) | {"media_type": None}
        try:
            # --ignore-no-formats-error keeps caption and uploader for image posts and carousels
            result = _run(
                ytdlp,
                "--dump-single-json",
                "--ignore-no-formats-error",
                "--no-warnings",
                *cookie_args,
                url,
            )
            meta = trim_meta(code, json.loads(result.stdout))
            if meta["media_type"] == "video":
                # the audio-only stream as served (no ffmpeg needed); a carousel with several
                # videos keeps only the first; upgrade to per-entry files if that ever matters
                out = work / "audio" / f"{code}.%(ext)s"
                _run(
                    ytdlp,
                    "-f",
                    "bestaudio/best",
                    "--no-playlist",
                    "--no-warnings",
                    "-o",
                    str(out),
                    *cookie_args,
                    url,
                )
        except (RuntimeError, OSError, json.JSONDecodeError) as e:
            meta["error"] = str(e)[-500:]
            prior = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            meta["retries"] = prior.get("retries", 0) + 1
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def run_fetch(
    work: Path,
    codes: list[str],
    cookies: Path | None,
    delay: float,
    ytdlp: str | list[str] = DEFAULT_YTDLP,
) -> dict[str, int]:
    posts = load_posts(work)
    counts = {"fetched": 0, "failed": 0}
    for i, code in enumerate(codes):
        if i and delay:
            time.sleep(delay)
        meta = fetch_one(code, posts[code]["url"], work, cookies, ytdlp)
        if meta["error"]:
            counts["failed"] += 1
            log.warning("fetch %s failed: %s", code, meta["error"].splitlines()[-1])
        else:
            counts["fetched"] += 1
            log.info("fetched %s (%s)", code, meta["media_type"])
    return counts
