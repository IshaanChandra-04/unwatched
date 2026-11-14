"""A stand-in for yt-dlp used by the tests. Behaviour is driven by environment variables."""

import os
import sys
from pathlib import Path


def main() -> int:
    args = sys.argv[1:]
    if os.environ.get("FAKE_YTDLP_FAIL") == "1":
        print(os.environ.get("FAKE_YTDLP_STDERR", "ERROR: login required"), file=sys.stderr)
        return 1
    if "--dump-single-json" in args:
        strict = os.environ.get("FAKE_YTDLP_REQUIRE_IGNORE") == "1"
        if strict and "--ignore-no-formats-error" not in args:
            print("ERROR: [Instagram] X: No video formats found!", file=sys.stderr)
            return 1
        print(os.environ["FAKE_YTDLP_JSON"])
        return 0
    if "-o" in args:
        template = args[args.index("-o") + 1]
        out = Path(template.replace("%(ext)s", "m4a"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.touch()
        return 0
    print("fake yt-dlp: unexpected arguments", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
