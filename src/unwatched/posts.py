"""The post store: one JSON record per shortcode in ``work/posts.jsonl``."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from unwatched.shortcode import url_for


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_posts(work: Path) -> dict[str, dict]:
    path = work / "posts.jsonl"
    if not path.exists():
        return {}
    posts = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            posts[rec["code"]] = rec
    return posts


def save_posts(work: Path, posts: dict[str, dict]) -> None:
    work.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(posts[code], ensure_ascii=False) for code in sorted(posts)]
    write_whole(work / "posts.jsonl", "".join(f"{line}\n" for line in lines))


def write_whole(path: Path, text: str) -> None:
    """Write through a temporary file and rename, so a crash never leaves half a file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def add_source(
    posts: dict[str, dict],
    code: str,
    source: dict,
    url: str | None = None,
    local_media: str | None = None,
) -> bool:
    """Record ``source`` for ``code``; return True when the post is new."""
    ts = source.get("ts")
    rec = posts.get(code)
    if rec is None:
        # shortcut: archived posts have no shortcode and so no URL; revisit if another
        # linkless kind appears
        if url is None and not code.startswith("archived-"):
            url = url_for(code)
        posts[code] = {
            "code": code,
            "url": url,
            "sources": [source],
            "first_seen": ts or now_iso(),
            "local_media": local_media,
        }
        return True
    if source not in rec["sources"]:
        rec["sources"].append(source)
    if ts and ts < rec["first_seen"]:
        rec["first_seen"] = ts
    if local_media and not rec["local_media"]:
        rec["local_media"] = local_media
    return False
