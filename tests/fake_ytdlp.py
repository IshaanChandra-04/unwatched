"""A stand-in for yt-dlp used by the tests. Behaviour is driven by environment variables."""

import json
import os
import sys
import time
from pathlib import Path


def main() -> int:
    args = sys.argv[1:]
    if os.environ.get("FAKE_YTDLP_LOG"):
        with open(os.environ["FAKE_YTDLP_LOG"], "a", encoding="utf-8") as f:
            f.write(json.dumps(args) + "\n")
    if os.environ.get("FAKE_YTDLP_SLEEP"):
        time.sleep(float(os.environ["FAKE_YTDLP_SLEEP"]))
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
    if "--write-thumbnail" in args:
        if os.environ.get("FAKE_YTDLP_FAIL_THUMBNAIL") == "1":
            print("ERROR: thumbnail", file=sys.stderr)
            return 1
        template = args[args.index("-o") + 1]
        slides = 2 if os.environ.get("FAKE_YTDLP_CAROUSEL") == "1" else 1
        for i in range(1, slides + 1):
            out = Path(template.replace("%(playlist_index|1)s", str(i)).replace("%(ext)s", "jpg"))
            out.parent.mkdir(parents=True, exist_ok=True)
            out.touch()
        return 0
    if "-o" in args:
        template = args[args.index("-o") + 1]
        fmt = args[args.index("-f") + 1] if "-f" in args else ""
        out = Path(template.replace("%(ext)s", "mp4" if "bestvideo" in fmt else "m4a"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.touch()
        return 0
    print("fake yt-dlp: unexpected arguments", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
