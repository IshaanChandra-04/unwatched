"""Render the digest input: everything Claude needs about each post, in one file."""

import json
from pathlib import Path

from unwatched.posts import load_posts, new_since, now_iso
from unwatched.state import load_state


def load_meta(work: Path, code: str) -> dict:
    path = work / "meta" / f"{code}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_transcript(work: Path, code: str) -> str | None:
    path = work / "transcripts" / f"{code}.txt"
    return path.read_text(encoding="utf-8").strip() if path.exists() else None


def _caption(rec: dict, meta: dict) -> str:
    if meta.get("caption"):
        return meta["caption"]
    return next((s["text"] for s in rec["sources"] if s.get("text")), "(none)")


def render(
    posts: dict[str, dict],
    metas: dict[str, dict],
    transcripts: dict[str, str | None],
    codes: list[str],
    generated: str,
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
            f"| {meta.get('media_type', '?')} | {rec['url'] or '(archived)'} | {sources} |"
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
            f"Caption: {_caption(rec, meta)}",
            "",
        ]
        transcript = transcripts.get(code)
        if transcript:
            lines += ["Transcript:", "", transcript]
        elif meta.get("media_type") == "video":
            lines.append("_video, not transcribed yet_")
        else:
            lines.append("_image post, no transcript_")
    return "\n".join(lines) + "\n"


def run_build(work: Path, out: Path, new_only: bool) -> int:
    posts = load_posts(work)
    if new_only:
        codes = new_since(posts, load_state(work)["last_digest"])
    else:
        codes = sorted(posts, key=lambda c: posts[c]["first_seen"])
    metas = {c: load_meta(work, c) for c in codes}
    transcripts = {c: load_transcript(work, c) for c in codes}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(posts, metas, transcripts, codes, now_iso()), encoding="utf-8")
    return len(codes)
