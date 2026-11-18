"""Command line entry point."""

import argparse
import logging
import re
import sys
from pathlib import Path

from unwatched import __version__, doctor, schedule
from unwatched.build import run_build
from unwatched.config import load_config
from unwatched.describe import ClaudeMissing, run_describe
from unwatched.digest import run_digest
from unwatched.fetch import COOKIES_PATH, DEFAULT_YTDLP, pending, pictures_todo, run_fetch, select
from unwatched.frames import run_frames
from unwatched.ingest import apply, ingest_export, ingest_links
from unwatched.posts import load_posts
from unwatched.run import EXIT_CAP, EXIT_DIGEST, EXIT_LOGIN, LOGIN_MESSAGE, run_all
from unwatched.state import load_state
from unwatched.transcribe import run_transcribe

_HELP = {
    "status": "show the last run and anything that needs you",
    "ingest": "collect posts from an export, links files, or live sweeps",
    "fetch": "download metadata, audio and video for new posts",
    "pictures": "download the slides of image posts through the browser",
    "frames": "pick the frames of each video that show something new",
    "transcribe": "transcribe downloaded audio locally",
    "describe": "have Claude write what is on screen in each post's pictures",
    "build": "write the digest input file",
    "digest": "update the master document through headless Claude",
    "run": "run the whole daily chain from a config file",
    "schedule": "install, remove or inspect the daily task",
    "login": "sign in to Instagram once in the tool's own browser window",
    "doctor": "check this machine for everything unwatched needs",
}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="unwatched",
        description="Turn the reels you saved or sent yourself into a document you will read.",
    )
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    subs = {}
    for name, text in _HELP.items():
        s = sub.add_parser(name, help=text)
        s.add_argument("--work", type=Path, default=Path("work"), help="work directory")
        subs[name] = s
    ingest = subs["ingest"]
    ingest.add_argument("exports", nargs="*", type=Path, metavar="EXPORT")
    ingest.add_argument("--links", action="append", type=Path, default=[], metavar="FILE")
    ingest.add_argument(
        "--seen", action="store_true", help="record these posts as already processed"
    )
    ingest.add_argument("--dm", action="append", default=[], metavar="URL", help="DM thread")
    ingest.add_argument("--saved", action="store_true", help="sweep the saved page")
    ingest.add_argument("--full", action="store_true", help="do not stop at known posts")
    ingest.add_argument("--username", help="Instagram username for the saved page")
    fetch = subs["fetch"]
    fetch.add_argument("--kinds", default="saved,dm", help="comma-separated; default saved,dm")
    fetch.add_argument("--thread", action="append", default=[], help="limit DM posts to a thread")
    fetch.add_argument("--since", help="only posts first seen after this ISO timestamp")
    fetch.add_argument("--max", type=int, default=300, help="stop before fetching more than this")
    fetch.add_argument("--delay", type=float, default=3, help="seconds between posts")
    fetch.add_argument("--only", nargs="*", metavar="CODE", help="fetch exactly these codes")
    fetch.add_argument("--cookies", type=Path, help=f"cookies.txt; default {COOKIES_PATH}")
    fetch.add_argument("--ytdlp", nargs="+", default=DEFAULT_YTDLP, help="yt-dlp command")
    transcribe = subs["transcribe"]
    transcribe.add_argument("--model", default="small", help="small (default) or large-v3-turbo")
    transcribe.add_argument("--language", default="en", help="language code, or auto")
    transcribe.add_argument("--only", nargs="*", metavar="CODE", help="re-run exactly these codes")
    for name in ("pictures", "frames", "describe"):
        subs[name].add_argument("--only", nargs="*", metavar="CODE", help="exactly these codes")
    subs["describe"].add_argument("--claude", default="claude", help="Claude Code executable")
    digest = subs["digest"]
    digest.add_argument("--profile", type=Path, required=True, help="interest profile")
    digest.add_argument("--master", type=Path, required=True, help="master document to update")
    digest.add_argument("--claude", default="claude", help="Claude Code executable")
    digest.add_argument("--max-turns", type=int, default=40)
    digest.add_argument("--max-posts", type=int, default=40, help="posts per digest run")
    run = subs["run"]
    run.add_argument("--config", type=Path, required=True, help="unwatched.toml")
    schedule = subs["schedule"]
    schedule.add_argument("action", choices=["install", "remove", "status"])
    schedule.add_argument("--at", default="15:00", help="daily time, HH:MM (default 15:00)")
    schedule.add_argument("--config", type=Path, help="config file the task runs with")
    subs["doctor"].add_argument("--config", type=Path, help="also check this unwatched.toml")
    build = subs["build"]
    build.add_argument("--out", type=Path, default=None, help="default: <work>/digest-input.md")
    build.add_argument("--new-only", action="store_true", help="only posts since the last digest")
    return p


def cmd_status(args) -> int:
    state = load_state(args.work)
    print(f"last run: {state['last_run'] or 'never'}")
    print(f"last digest: {state['last_digest'] or 'never'}")
    print(f"posts: {len(load_posts(args.work))}")
    if state["last_error"]:
        print(f"action needed: {state['last_error']}")
    return 0


def cmd_ingest(args) -> int:
    if not (args.exports or args.links or args.dm or args.saved):
        print("ingest needs an export, --links, --dm or --saved", file=sys.stderr)
        return 2
    found = []
    for export in args.exports:
        found += ingest_export(export)
    for links in args.links:
        found += ingest_links(links)
    if args.dm or args.saved:
        from unwatched.browser import LoginRequired, sweep_dm, sweep_saved

        known = set(load_posts(args.work))
        try:
            for url in args.dm:
                found += sweep_dm(url, known, full=args.full)
            if args.saved:
                found += sweep_saved(known, full=args.full, username=args.username)
        except LoginRequired:
            print(LOGIN_MESSAGE, file=sys.stderr)
            return EXIT_LOGIN
    counts = apply(args.work, found, seen=args.seen)
    for label in sorted(counts):
        print(f"{label}: {counts[label]}")
    print(f"posts: {len(load_posts(args.work))}")
    return 0


def cmd_build(args) -> int:
    out = args.out or args.work / "digest-input.md"
    codes = run_build(args.work, out, args.new_only)
    print(f"wrote {out} with {len(codes)} posts")
    return 0


def cmd_fetch(args) -> int:
    posts = load_posts(args.work)
    only = set(args.only) if args.only else None
    threads = set(args.thread) or None
    kinds = {k.strip() for k in args.kinds.split(",")}
    codes = select(posts, kinds, threads, args.since, only)
    todo = codes if only else pending(args.work, codes)  # --only re-fetches on purpose
    if len(todo) > args.max:
        print(f"selected {len(todo)} posts, cap is {args.max}; ", end="")
        print(f"rerun with --max {len(todo)} to continue")
        return EXIT_CAP
    cookies = args.cookies or (COOKIES_PATH if COOKIES_PATH.exists() else None)
    counts = run_fetch(args.work, todo, cookies, args.delay, args.ytdlp)
    print(f"fetched {counts['fetched']} failed {counts['failed']}")
    return 0


def cmd_pictures(args) -> int:
    posts = load_posts(args.work)
    codes = sorted(args.only) if args.only else pictures_todo(args.work, posts)
    if not codes:
        print("nothing to fetch")
        return 0
    from unwatched.browser import LoginRequired, fetch_pictures

    try:
        counts = fetch_pictures(args.work, codes)
    except LoginRequired:
        print(LOGIN_MESSAGE, file=sys.stderr)
        return EXIT_LOGIN
    print(f"fetched {counts['fetched']} failed {counts['failed']}")
    return 0


def cmd_frames(args) -> int:
    only = set(args.only) if args.only else None
    counts = run_frames(args.work, load_posts(args.work), only)
    print(f"sampled {counts['sampled']} failed {counts['failed']}")
    return 0


def cmd_describe(args) -> int:
    only = set(args.only) if args.only else None
    try:
        counts = run_describe(args.work, args.claude, only)
    except ClaudeMissing as e:
        print(e, file=sys.stderr)
        return EXIT_DIGEST
    print(f"described {counts['described']} failed {counts['failed']}")
    return 0


def cmd_transcribe(args) -> int:
    language = None if args.language == "auto" else args.language
    only = set(args.only) if args.only else None
    n = run_transcribe(args.work, load_posts(args.work), args.model, language, only)
    print(f"transcribed {n}")
    return 0


def cmd_login(args) -> int:
    from unwatched.browser import export_cookies, login

    print("A browser window is opening. Sign in to Instagram there; nothing is typed for you.")
    if not login():
        print("no sign-in detected within 10 minutes", file=sys.stderr)
        return 1
    export_cookies()
    print("signed in")
    return 0


def cmd_digest(args) -> int:
    ok, summary = run_digest(
        args.work, args.profile, args.master, args.claude, args.max_turns, args.max_posts
    )
    print(summary)
    return 0 if ok else EXIT_DIGEST


def cmd_schedule(args) -> int:
    try:
        if args.action == "install":
            if not args.config:
                print("schedule install needs --config", file=sys.stderr)
                return 2
            if not re.fullmatch(r"\d{2}:\d{2}", args.at):
                print("--at must be HH:MM, for example 15:00", file=sys.stderr)
                return 2
            try:
                load_config(args.config)
            except (OSError, ValueError) as e:  # a TOML syntax error is a ValueError
                print(f"cannot read {args.config}: {e}", file=sys.stderr)
                return 2
            schedule.install(args.at, args.config)
            print(f"registered '{schedule.TASK_NAME}' daily at {args.at}")
        elif args.action == "remove":
            schedule.remove()
            print(f"removed '{schedule.TASK_NAME}'")
        else:
            for key, value in schedule.status().items():
                print(f"{key}: {value}")
    except (RuntimeError, FileNotFoundError) as e:  # a missing crontab or launchctl, say
        print(str(e), file=sys.stderr)
        return 1
    return 0


def cmd_doctor(args) -> int:
    cfg = None
    if args.config:
        try:
            cfg = load_config(args.config)
        except (OSError, ValueError) as e:
            print(f"cannot read {args.config}: {e}", file=sys.stderr)
            return 2
    results = doctor.checks(cfg)
    for name, ok, detail in results:
        print(f"{'ok ' if ok else 'fix'}  {name}: {detail}")
    return 0 if all(ok for _, ok, _ in results) else 1


def cmd_run(args) -> int:
    try:
        cfg = load_config(args.config)
    except (OSError, ValueError) as e:  # a TOML syntax error is a ValueError
        print(f"cannot read {args.config}: {e}", file=sys.stderr)
        return 2
    return run_all(cfg)


_COMMANDS = {
    "status": cmd_status,
    "ingest": cmd_ingest,
    "build": cmd_build,
    "fetch": cmd_fetch,
    "pictures": cmd_pictures,
    "frames": cmd_frames,
    "transcribe": cmd_transcribe,
    "describe": cmd_describe,
    "login": cmd_login,
    "digest": cmd_digest,
    "schedule": cmd_schedule,
    "run": cmd_run,
    "doctor": cmd_doctor,
}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    # progress for hand-run commands; `run` replaces this with its dated log file
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        return _COMMANDS[args.cmd](args)
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
