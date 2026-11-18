"""Render the digest input: everything Claude needs about each post, in one file."""

import json
from pathlib import Path

from unwatched.posts import load_posts, now_iso
from unwatched.state import load_state, save_state


def load_meta(work: Path, code: str) -> dict:
    path = work / "meta" / f"{code}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_transcript(work: Path, code: str) -> str | None:
    path = work / "transcripts" / f"{code}.txt"
    return path.read_text(encoding="utf-8").strip() if path.exists() else None


def load_screen(work: Path, code: str) -> str | None:
    """The on-screen report `describe` wrote for the post's frames or slides."""
    path = work / "frames" / f"{code}.md"
    return path.read_text(encoding="utf-8").strip() if path.exists() else None


def _quote(text: str) -> str:
    """Mark every line, so text written by strangers reads as data, not as instructions."""
    return "\n".join(f"> {line}" for line in text.splitlines())


def _caption_text(rec: dict, meta: dict) -> str | None:
    if meta.get("caption"):
        return meta["caption"]
    return next((s["text"] for s in rec["sources"] if s.get("text")), None)


def _caption(rec: dict, meta: dict) -> str:
    return _caption_text(rec, meta) or "(none)"


def materials(work: Path, code: str, rec: dict, meta: dict) -> list[str]:
    """What the digest can read about a post; the post is presented again when this grows."""
    out = []
    if _caption_text(rec, meta):
        out.append("caption")
    if (work / "transcripts" / f"{code}.txt").exists():
        out.append("transcript")
    if (work / "frames" / f"{code}.md").exists():
        out.append("frames")
    return out


def due(work: Path, posts: dict[str, dict], state: dict) -> list[str]:
    """Posts the digest has not seen, or saw with less material, oldest first.

    A state written before 0.2 has no record per post; its posts from before the last digest
    are recorded with what they have now, so they are not presented a second time.
    """
    digested = state.setdefault("digested", {})
    if not digested and state.get("last_digest"):
        for code, rec in posts.items():
            if rec["first_seen"] <= state["last_digest"]:
                digested[code] = materials(work, code, rec, load_meta(work, code))
    codes = [
        code
        for code, rec in posts.items()
        if code not in digested
        or set(materials(work, code, rec, load_meta(work, code))) - set(digested[code])
    ]
    return sorted(codes, key=lambda c: posts[c]["first_seen"])


def render(
    posts: dict[str, dict],
    metas: dict[str, dict],
    transcripts: dict[str, str | None],
    codes: list[str],
    generated: str,
    screens: dict[str, str | None] | None = None,
) -> str:
    lines = [
        "# unwatched digest input",
        "",
        f"Generated {generated} · {len(codes)} posts",
        "",
        "| Date | Author | Type | Link | Sources |",
        "|---|---|---|---|---|",
    ]
    for code in codes:
        rec, meta = posts[code], metas.get(code, {})
        sources = "; ".join(f"{s['kind']}: {s['name']}" for s in rec["sources"])
        lines.append(
            f"| {rec['first_seen'][:10]} | {meta.get('uploader') or 'unknown'} "
            f"| {meta.get('media_type') or '?'} | {rec['url'] or '(archived)'} | {sources} |"
        )
    for code in codes:
        rec, meta = posts[code], metas.get(code, {})
        sources = "; ".join(f"{s['kind']} ({s['name']}, {s['via']})" for s in rec["sources"])
        lines += [
            "",
            f"## {code} · @{meta.get('uploader') or 'unknown'} · {rec['first_seen'][:10]}",
            "",
            f"Link: {rec['url'] or '(archived post, no link)'}",
            f"Sources: {sources}",
            "Caption:",
            "",
            _quote(_caption(rec, meta)),
            "",
        ]
        transcript = transcripts.get(code)
        screen = (screens or {}).get(code)
        if transcript:
            lines += ["Transcript:", "", _quote(transcript)]
        elif transcript == "" and meta.get("media_type") == "video":
            lines.append("_video, no speech detected_")
        elif meta.get("media_type") == "video":
            lines.append("_video, not transcribed yet_")
        elif not screen:
            lines.append("_image post, no transcript_")
        if screen:
            lines += ["", "On screen:", "", _quote(screen)]
    return "\n".join(lines) + "\n"


def run_build(work: Path, out: Path, new_only: bool, max_posts: int | None = None) -> list[str]:
    """Write the digest input for the due posts (or all of them); return the codes written."""
    posts = load_posts(work)
    if new_only:
        state = load_state(work)
        codes = due(work, posts, state)[:max_posts]
        save_state(work, state)  # keeps a migrated pre-0.2 record
    else:
        codes = sorted(posts, key=lambda c: posts[c]["first_seen"])
    metas = {c: load_meta(work, c) for c in codes}
    transcripts = {c: load_transcript(work, c) for c in codes}
    screens = {c: load_screen(work, c) for c in codes}
    out.parent.mkdir(parents=True, exist_ok=True)
    text = render(posts, metas, transcripts, codes, now_iso(), screens)
    out.write_text(text, encoding="utf-8")
    return codes
