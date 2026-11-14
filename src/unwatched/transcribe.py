"""Transcribe downloaded audio locally with faster-whisper."""

import logging
from functools import cache
from pathlib import Path

log = logging.getLogger("unwatched")


def audio_path(work: Path, code: str, posts: dict[str, dict]) -> Path | None:
    audio = work / "audio" / f"{code}.m4a"
    if audio.exists():
        return audio
    local = posts.get(code, {}).get("local_media")
    if local and Path(local).exists():
        return Path(local)
    return None


def todo(work: Path, posts: dict[str, dict], only: set[str] | None) -> list[str]:
    codes = sorted(only) if only is not None else sorted(posts)
    out = []
    for code in codes:
        if audio_path(work, code, posts) is None:
            continue
        if only is None and (work / "transcripts" / f"{code}.txt").exists():
            continue
        out.append(code)
    return out


@cache
def _model(name: str):
    from faster_whisper import WhisperModel

    return WhisperModel(name, device="cpu", compute_type="int8")


def transcribe_file(path: Path, model: str, language: str | None) -> str:
    segments, _info = _model(model).transcribe(
        str(path),
        language=language,
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    return "\n".join(s.text.strip() for s in segments)


def run_transcribe(
    work: Path,
    posts: dict[str, dict],
    model: str,
    language: str | None,
    only: set[str] | None,
) -> int:
    (work / "transcripts").mkdir(parents=True, exist_ok=True)
    codes = todo(work, posts, only)
    for code in codes:
        text = transcribe_file(audio_path(work, code, posts), model, language)
        (work / "transcripts" / f"{code}.txt").write_text(text, encoding="utf-8")
        log.info("transcribed %s with %s (%d chars)", code, model, len(text))
    return len(codes)
