"""Pick the frames of a video that show something new: a few pictures per post for Claude."""

import logging
import shutil
from pathlib import Path

from unwatched.fetch import media_file

MAX_FRAMES = 12  # shortcut: enough for a reel's scenes; raise when long videos arrive
_CHANGE = 12  # mean grey difference (of 255) between thumbnails that counts as a new scene
_THUMB = (16, 28)
_WIDTH = 720  # wide enough to read on-screen text, small enough to keep the image cheap
log = logging.getLogger("unwatched")


def _grey(img) -> list[int]:
    return list(img.resize(_THUMB).convert("L").tobytes())


def _diff(a: list[int], b: list[int]) -> float:
    return sum(abs(x - y) for x, y in zip(a, b, strict=True)) / len(a)


def sample(video: Path, out: Path, max_frames: int = MAX_FRAMES) -> list[Path]:
    """Save the frames where the picture changes, the first one always, ``max_frames`` at most.

    A candidate is taken about every duration/40 seconds (at least every half second) and kept
    when it differs enough from the last kept frame; over the cap, the least different go.
    """
    import av

    kept: list[tuple[float, object]] = []  # (difference to the previous kept frame, image)
    with av.open(str(video)) as container:
        stream = container.streams.video[0]
        duration = float(stream.duration * stream.time_base) if stream.duration else None
        if duration is None and container.duration:
            duration = container.duration / 1_000_000
        step = max(0.5, (duration or 0) / 40)
        next_t, last = 0.0, None
        for frame in container.decode(stream):
            t = frame.time or 0.0
            if t < next_t:
                continue
            next_t = t + step
            img = frame.to_image()
            grey = _grey(img)
            if last is None or (d := _diff(grey, last)) > _CHANGE:
                kept.append((float("inf") if last is None else d, img))
                last = grey
    if len(kept) > max_frames:
        by_change = sorted(range(1, len(kept)), key=lambda i: kept[i][0], reverse=True)
        kept = [kept[0]] + [kept[i] for i in sorted(by_change[: max_frames - 1])]
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, (_, img) in enumerate(kept, 1):
        if img.width > _WIDTH:
            img = img.resize((_WIDTH, round(img.height * _WIDTH / img.width)))
        path = out / f"{i:02d}.jpg"
        img.convert("RGB").save(path, quality=80)
        paths.append(path)
    return paths


def run_frames(work: Path, posts: dict[str, dict], only: set[str] | None) -> dict[str, int]:
    """Sample every fetched video without frames yet; ``only`` re-samples exactly those codes."""
    counts = {"sampled": 0, "failed": 0}
    for code in sorted(only) if only is not None else sorted(posts):
        video = media_file(work, "video", code)
        out = work / "frames" / code
        if video is None or (only is None and out.exists()):
            continue
        shutil.rmtree(out, ignore_errors=True)
        try:
            n = len(sample(video, out))
            counts["sampled"] += 1
            log.info("frames %s: %d", code, n)
        except Exception as e:  # a broken download must not stop the run or be retried daily
            out.mkdir(parents=True, exist_ok=True)
            counts["failed"] += 1
            log.warning("frames %s failed: %s", code, e)
    return counts
