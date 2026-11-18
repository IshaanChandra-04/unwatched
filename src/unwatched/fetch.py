"""Fetch metadata and media for posts with yt-dlp, one post at a time."""

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
# the video-only stream is enough for frames; the audio-only stream feeds the transcript
VIDEO_FORMAT = "bestvideo[height<=720]/bestvideo/best[height<=720]/best"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
TIMEOUT_S = 300  # one stalled download must not hold the daily run
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


def media_file(work: Path, folder: str, code: str) -> Path | None:
    return next(iter(sorted((work / folder).glob(f"{code}.*"))), None)


def pictures(work: Path, code: str) -> list[Path]:
    """The pictures of a post (carousel slides, or the sampled frames of a video), in order."""
    folder = work / "frames" / code
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)


def _missing_media(work: Path, code: str, meta: dict) -> bool:
    """A post fetched before 0.2 has no video or pictures yet; a failed one is left to retries."""
    if meta.get("error"):
        return False
    if meta.get("media_type") == "video":
        return media_file(work, "video", code) is None
    if meta.get("media_type") == "image":
        return not pictures(work, code)
    return False


def pending(work: Path, codes: list[str]) -> list[str]:
    """Codes not fetched yet, failed fewer than three times, or still missing their media."""
    out = []
    for code in codes:
        path = work / "meta" / f"{code}.json"
        meta = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        if (
            meta is None
            or (meta.get("error") and meta.get("retries", 0) < 3)
            or _missing_media(work, code, meta)
        ):
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
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"yt-dlp timed out after {TIMEOUT_S} s") from None
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"yt-dlp exited {result.returncode}")
    return result


def number_pictures(folder: Path) -> None:
    """Name the pictures 01.jpg, 02.jpg, ... in slide order; webp becomes jpg for the readers."""
    from PIL import Image

    files = [p for p in folder.iterdir() if p.is_file()]
    files.sort(key=lambda p: (int(p.stem) if p.stem.isdigit() else 10**6, p.name))
    for i, path in enumerate(files, 1):
        if path.suffix.lower() == ".webp":
            Image.open(path).convert("RGB").save(folder / f"{i:02d}.jpg", quality=90)
            path.unlink()
        elif path != (target := folder / f"{i:02d}{path.suffix.lower()}"):
            path.rename(target)


def fetch_one(
    code: str,
    url: str | None,
    work: Path,
    cookies: Path | None,
    ytdlp: str | list[str] = DEFAULT_YTDLP,
) -> dict:
    """Write ``meta/<code>.json``; for videos ``audio/`` and ``video/`` files, for image posts the
    cover picture in ``frames/<code>/``. Files that exist are not downloaded again. Never raises.
    """
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
            common = ["--no-playlist", "--no-warnings", *cookie_args, url]
            if meta["media_type"] == "video":
                # shortcut: a carousel with several videos keeps only the first; upgrade to
                # per-entry files if that ever matters
                if media_file(work, "audio", code) is None:
                    out = work / "audio" / f"{code}.%(ext)s"
                    _run(ytdlp, "-f", "bestaudio/best", "-o", str(out), *common)
                if media_file(work, "video", code) is None:
                    out = work / "video" / f"{code}.%(ext)s"
                    _run(ytdlp, "-f", VIDEO_FORMAT, "-o", str(out), *common)
                    if media_file(work, "video", code) is None:
                        raise RuntimeError("no video file written")
            elif meta["media_type"] == "image" and not pictures(work, code):
                # yt-dlp has only the cover picture of an image post; the slides and the caption
                # come through the browser in the `pictures` stage
                folder = work / "frames" / code
                _run(
                    ytdlp,
                    "--write-thumbnail",
                    "--skip-download",
                    "--ignore-no-formats-error",
                    "--no-warnings",
                    "-o",
                    str(folder / "%(playlist_index|1)s.%(ext)s"),
                    *cookie_args,
                    url,
                )
                if folder.is_dir():
                    number_pictures(folder)
                if not pictures(work, code):
                    raise RuntimeError("no picture written")
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
