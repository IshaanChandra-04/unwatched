"""Command line entry point."""

import argparse
import sys
from pathlib import Path

from unwatched import __version__
from unwatched.ingest import apply, ingest_export, ingest_links
from unwatched.posts import load_posts
from unwatched.state import load_state

EXIT_LOGIN = 3
EXIT_CAP = 4
EXIT_DIGEST = 5

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
    if not args.exports and not args.links:
        print("ingest needs an export or --links", file=sys.stderr)
        return 2
    found = []
    for export in args.exports:
        found += ingest_export(export)
    for links in args.links:
        found += ingest_links(links)
    counts = apply(args.work, found, seen=args.seen)
    for label in sorted(counts):
        print(f"{label}: {counts[label]}")
    print(f"posts: {len(load_posts(args.work))}")
    return 0


_COMMANDS = {"status": cmd_status, "ingest": cmd_ingest}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    handler = _COMMANDS.get(args.cmd)
    if handler is None:
        print(f"{args.cmd}: not implemented yet", file=sys.stderr)
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
