"""A stand-in for `claude -p` used by the tests.

Reads the prompt from stdin, appends a line to the file named on its ``Master:`` line, and prints
the completion marker. With ``FAKE_CLAUDE_SILENT=1`` it does nothing and prints nothing.
"""

import json
import os
import re
import sys
from pathlib import Path


def main() -> int:
    if os.environ.get("FAKE_CLAUDE_ARGV"):
        Path(os.environ["FAKE_CLAUDE_ARGV"]).write_text(json.dumps(sys.argv[1:]), encoding="utf-8")
    if os.environ.get("FAKE_CLAUDE_SILENT") == "1":
        return 0
    prompt = sys.stdin.read()
    match = re.search(r"^Master: (.+)$", prompt, re.M)
    if not match or "Mode: headless." not in prompt:
        return 0
    master = Path(match.group(1).strip())
    with master.open("a", encoding="utf-8") as f:
        f.write("digested\n")
    print("UNWATCHED_DIGEST_DONE kept=2 total=5")
    return 0


if __name__ == "__main__":
    sys.exit(main())
