"""The daily chain: ingest, fetch, transcribe, build, digest, with a log and a one-line summary."""

import logging
from datetime import UTC, datetime
from pathlib import Path

from unwatched.build import run_build
from unwatched.digest import run_digest
from unwatched.fetch import COOKIES_PATH, DEFAULT_YTDLP, pending, run_fetch, select
from unwatched.ingest import apply, ingest_export, ingest_links
from unwatched.posts import load_posts, now_iso
from unwatched.state import load_state, save_state
from unwatched.transcribe import run_transcribe

EXIT_LOGIN = 3
EXIT_CAP = 4
EXIT_DIGEST = 5
LOGIN_MESSAGE = "sign-in expired, run: unwatched login"
log = logging.getLogger("unwatched")


def _setup_logging(work: Path) -> None:
    (work / "logs").mkdir(parents=True, exist_ok=True)
    path = work / "logs" / f"{datetime.now(UTC):%Y-%m-%d}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(path, encoding="utf-8"), logging.StreamHandler()],
        force=True,
    )
    for name in ("huggingface_hub", "faster_whisper"):  # chatty at INFO
        logging.getLogger(name).setLevel(logging.WARNING)


def _collect_live(cfg: dict, work: Path) -> tuple[list, list[str]]:
    """Sweep every live source; one that fails is reported, not allowed to lose the others."""
    from unwatched.browser import LoginRequired, export_cookies, sweep_dm, sweep_saved

    known = set(load_posts(work))
    export_cookies()  # refresh the cookies yt-dlp will use; raises LoginRequired if signed out
    found, errors = [], []

    def attempt(label, sweep, *args, **kwargs):
        try:
            found.extend(sweep(*args, **kwargs))
        except LoginRequired:
            raise
        except Exception as e:  # a page that never loads must not lose the other sources' posts
            log.exception("%s failed", label)
            errors.append(f"{label} failed: {type(e).__name__}: {e}")

    for url in cfg["sources"]["dm"]:
        attempt("dm sweep", sweep_dm, url, known)
    if cfg["sources"]["saved"]:
        attempt("saved sweep", sweep_saved, known, username=cfg["username"])
    return found, errors


def run_all(cfg: dict, ytdlp: str | list[str] = DEFAULT_YTDLP) -> int:
    work = Path(cfg["work"])
    _setup_logging(work)
    state = load_state(work)

    def finish(code: int, error: str | None, summary: str) -> int:
        state.update(last_run=now_iso(), last_error=error, last_summary=summary)
        save_state(work, state)
        log.info("%s%s", summary, f"; {error}" if error else "")
        return code

    try:
        return _chain(cfg, work, ytdlp, finish)
    except Exception as e:  # the scheduled run has nobody watching stderr
        log.exception("run crashed")
        return finish(1, f"{type(e).__name__}: {e}", "run crashed")


def _chain(cfg: dict, work: Path, ytdlp, finish) -> int:
    sources = cfg["sources"]
    found, errors = [], []
    for export in sources["export"]:
        found += ingest_export(Path(export))
    for links in sources["links"]:
        found += ingest_links(Path(links))
    if sources["dm"] or sources["saved"]:
        from unwatched.browser import LoginRequired

        try:
            live, errors = _collect_live(cfg, work)
            found += live
        except LoginRequired:
            return finish(EXIT_LOGIN, LOGIN_MESSAGE, "ingest stopped: sign-in expired")

    before = len(load_posts(work))
    apply(work, found)
    posts = load_posts(work)
    new = len(posts) - before

    fetch_cfg = cfg["fetch"]
    todo = pending(work, select(posts, set(fetch_cfg["kinds"]), None, None, None))
    if len(todo) > fetch_cfg["max"]:
        errors.append(
            f"{len(todo)} posts selected, cap is {fetch_cfg['max']}; run "
            f"`unwatched fetch --work {work} --max {len(todo)}` to continue"
        )
        return finish(EXIT_CAP, "; ".join(errors), f"ingested {new} new, fetch stopped at cap")
    cookies = COOKIES_PATH if COOKIES_PATH.exists() else None
    counts = run_fetch(work, todo, cookies, fetch_cfg["delay"], ytdlp)
    if todo and counts["failed"] == len(todo):
        errors.append(f"every fetch failed ({len(todo)} posts); check the log and the cookies")

    t_cfg = cfg["transcribe"]
    language = None if t_cfg["language"] == "auto" else t_cfg["language"]
    transcribed = run_transcribe(work, load_posts(work), t_cfg["model"], language, None)
    run_build(work, work / "digest-input.md", new_only=True)

    code, digest_result = 0, "skipped"
    if cfg["digest"] and cfg["profile"] and cfg["master"]:
        ok, summary = run_digest(
            work, Path(cfg["profile"]), Path(cfg["master"]), cfg["claude"], cfg["digest_max_turns"]
        )
        digest_result = "ok" if ok else "failed"
        if not ok:
            code = EXIT_DIGEST
            errors.append(summary.splitlines()[0])
    return finish(
        code,
        "; ".join(errors) or None,
        f"ingested {new} new, fetched {counts['fetched']}, failed {counts['failed']}, "
        f"transcribed {transcribed}, digest {digest_result}",
    )
