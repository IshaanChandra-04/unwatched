"""Collect posts from a data export, a links file, or live sweeps into the store."""

import json
import logging
import re
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from unwatched.posts import add_source, load_posts, now_iso, save_posts
from unwatched.shortcode import codes_from_text
from unwatched.state import load_state, save_state

Found = tuple[str, dict, str | None]  # (code, source, local_media)
log = logging.getLogger("unwatched")
_MESSAGE_FILE = re.compile(r"messages/inbox/[^/]+/message_\d+\.json$")


def fix_text(s: str) -> str:
    """Repair the export's UTF-8-read-as-Latin-1 text; leave anything else alone."""
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def iso_from_epoch(value: int | float, unit: str) -> str:
    secs = value / 1000 if unit == "ms" else value
    return datetime.fromtimestamp(secs, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def iter_export_files(path: Path) -> Iterator[tuple[str, bytes]]:
    if path.is_dir():
        for p in path.rglob("*.json"):
            yield p.relative_to(path).as_posix(), p.read_bytes()
        return
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.endswith(".json"):
                yield name, z.read(name)


def _hrefs(obj, title: str | None = None) -> Iterator[tuple[str, int | None, str | None]]:
    """Every ``href`` in the JSON with its sibling ``timestamp`` and the nearest ``title``."""
    if isinstance(obj, dict):
        if isinstance(obj.get("title"), str):
            title = obj["title"]
        if isinstance(obj.get("href"), str):
            yield obj["href"], obj.get("timestamp"), title
        for v in obj.values():
            yield from _hrefs(v, title)
    elif isinstance(obj, list):
        for v in obj:
            yield from _hrefs(v, title)


def _source(kind: str, name: str, ts: str | None, text: str | None = None) -> dict:
    src = {"kind": kind, "name": name, "via": "export", "ts": ts}
    if text:
        src["text"] = text
    return src


def _from_hrefs(data: dict, kind: str, name: str | None) -> list[Found]:
    out: list[Found] = []
    for href, ts, title in _hrefs(data):
        label = name or (fix_text(title) if title else "collection")
        for code in codes_from_text(href):
            out.append((code, _source(kind, label, iso_from_epoch(ts, "s") if ts else None), None))
    return out


def parse_saved(data: dict, name: str) -> list[Found]:
    return _from_hrefs(data, "saved", name)


def parse_liked(data: dict) -> list[Found]:
    return _from_hrefs(data, "liked", "likes")


def parse_messages(data: dict) -> list[Found]:
    name = fix_text(data.get("title") or "thread")
    out: list[Found] = []
    for m in data.get("messages", []):
        share = m.get("share") or {}
        text = " ".join(filter(None, [share.get("link"), m.get("content")]))
        ts = iso_from_epoch(m["timestamp_ms"], "ms") if m.get("timestamp_ms") else None
        caption = fix_text(share["share_text"]) if share.get("share_text") else None
        for code in codes_from_text(text):
            out.append((code, _source("dm", name, ts, caption), None))
    return out


def parse_archived(data: dict, media_root: str) -> list[Found]:
    out: list[Found] = []
    for item in data.get("ig_archived_post_media", []):
        for m in item.get("media", []):
            created = int(m["creation_timestamp"])
            title = fix_text(m["title"]) if m.get("title") else None
            src = _source("archived", "archive", iso_from_epoch(created, "s"), title)
            out.append((f"archived-{created}", src, media_root + m["uri"]))
    return out


def ingest_export(path: Path) -> list[Found]:
    # a zip's media is addressed as "<zip>!<member>" and extracted by apply()
    media_root = f"{path}/" if path.is_dir() else f"{path}!"
    out: list[Found] = []
    for name, raw in iter_export_files(path):
        data = json.loads(raw.decode("utf-8"))
        if name.endswith("saved_posts.json"):
            out += parse_saved(data, "saved")
        elif name.endswith("saved_collections.json"):
            out += _from_hrefs(data, "saved", None)
        elif name.endswith("liked_posts.json"):
            out += parse_liked(data)
        elif name.endswith("archived_posts.json"):
            out += parse_archived(data, media_root)
        elif _MESSAGE_FILE.search(name):
            out += parse_messages(data)
    return out


def ingest_links(path: Path) -> list[Found]:
    src = {"kind": "links", "name": path.name, "via": "file", "ts": None}
    return [(code, src, None) for code in codes_from_text(path.read_text(encoding="utf-8"))]


def _materialize(work: Path, code: str, local_media: str) -> str | None:
    """Extract an archived post's media from its export zip; None when the zip lacks it."""
    zip_path, sep, member = local_media.partition("!")
    if not sep or not Path(zip_path).is_file():
        return local_media
    with zipfile.ZipFile(zip_path) as z:
        # the export's uri is relative to the export root, which may sit inside a top folder
        name = next((n for n in z.namelist() if n.endswith(member)), None)
        if name is None:
            log.warning("%s: media %s is not in %s (another export part?)", code, member, zip_path)
            return None
        out = work / "archived" / f"{code}{Path(member).suffix}"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(z.read(name))
    return str(out)


def apply(work: Path, found: list[Found], seen: bool = False) -> dict[str, int]:
    """Merge ``found`` into the store; return how many items each source contributed."""
    posts = load_posts(work)
    counts: dict[str, int] = {}
    new: list[str] = []
    for code, src, local in found:
        label = f"{src['kind']}:{src['name']}"
        counts[label] = counts.get(label, 0) + 1
        if local:
            local = _materialize(work, code, local)
        if add_source(posts, code, src, local_media=local):
            new.append(code)
    if seen:
        state = load_state(work)
        if state["last_digest"] is None:
            state["last_digest"] = now_iso()
            save_state(work, state)
        (work / "meta").mkdir(parents=True, exist_ok=True)
        for code in new:
            # dated no later than the last digest, so the next digest does not pick them up
            posts[code]["first_seen"] = min(posts[code]["first_seen"], state["last_digest"])
            meta = json.dumps({"code": code, "skipped": "seeded"})
            (work / "meta" / f"{code}.json").write_text(meta, encoding="utf-8")
    save_posts(work, posts)
    return counts
