"""Command line entry point."""

import argparse
import sys
from pathlib import Path

from unwatched import __version__
from unwatched.build import run_build
from unwatched.fetch import COOKIES_PATH, pending, run_fetch, select
from unwatched.ingest import apply, ingest_export, ingest_links
from unwatched.posts import load_posts
from unwatched.state import load_state
from unwatched.transcribe import run_transcribe

EXIT_LOGIN = 3
EXIT_CAP = 4
EXIT_DIGEST = 5
LOGIN_MESSAGE = "sign-in expired, run: unwatched login"

_HELP = {
    "status": "show the last run and anything that needs you",
    "ingest": "collect posts from an export, links files, or live sweeps",
    "fetch": "download metadata and audio for new posts",
    "transcribe": "transcribe downloaded audio locally",
    "build": "write the digest input file",
    "digest": "update the master document through headless Claude",
    "run": "run the whole daily chain from a config file",
    "schedule": "install, remove or inspect the daily task",
    "login": "sign in to Instagram once in the tool's own browser window",
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
    fetch.add_argument("--ytdlp", default="yt-dlp", help="yt-dlp executable")
    transcribe = subs["transcribe"]
    transcribe.add_argument("--model", default="small", help="small (default) or large-v3-turbo")
    transcribe.add_argument("--language", default="en", help="language code, or auto")
    transcribe.add_argument("--only", nargs="*", metavar="CODE", help="re-run exactly these codes")
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
    n = run_build(args.work, out, args.new_only)
    print(f"wrote {out} with {n} posts")
    return 0


def cmd_fetch(args) -> int:
    posts = load_posts(args.work)
    only = set(args.only) if args.only else None
    threads = set(args.thread) or None
    todo = pending(args.work, select(posts, set(args.kinds.split(",")), threads, args.since, only))
    if len(todo) > args.max:
        print(f"selected {len(todo)} posts, cap is {args.max}; ", end="")
        print(f"rerun with --max {len(todo)} to continue")
        return EXIT_CAP
    cookies = args.cookies or (COOKIES_PATH if COOKIES_PATH.exists() else None)
    counts = run_fetch(args.work, todo, cookies, args.delay, args.ytdlp)
    print(f"fetched {counts['fetched']} failed {counts['failed']}")
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


_COMMANDS = {
    "status": cmd_status,
    "ingest": cmd_ingest,
    "build": cmd_build,
    "fetch": cmd_fetch,
    "transcribe": cmd_transcribe,
    "login": cmd_login,
}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    handler = _COMMANDS.get(args.cmd)
    if handler is None:
        print(f"{args.cmd}: not implemented yet", file=sys.stderr)
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
