"""A stand-in for `claude -p` used by the tests.

Reads the prompt from stdin. For a digest prompt it appends a line to the file named on the
``Master:`` line and prints the completion marker; for a describe prompt (frames of one post)
it prints a short on-screen report. ``FAKE_CLAUDE_SILENT=1`` does nothing and prints nothing;
``FAKE_CLAUDE_DESCRIBE_FAIL=1`` makes describe prompts exit 1; ``FAKE_CLAUDE_ARGV`` and
``FAKE_CLAUDE_CWD`` name files that receive the arguments and the working directory.
"""

import json
import os
import re
import sys
import time
from pathlib import Path


def main() -> int:
    if os.environ.get("FAKE_CLAUDE_ARGV"):
        Path(os.environ["FAKE_CLAUDE_ARGV"]).write_text(json.dumps(sys.argv[1:]), encoding="utf-8")
    if os.environ.get("FAKE_CLAUDE_CWD"):
        Path(os.environ["FAKE_CLAUDE_CWD"]).write_text(os.getcwd(), encoding="utf-8")
    if os.environ.get("FAKE_CLAUDE_SLEEP"):
        time.sleep(float(os.environ["FAKE_CLAUDE_SLEEP"]))
    if os.environ.get("FAKE_CLAUDE_SILENT") == "1":
        return 0
    prompt = sys.stdin.read()
    if "frames of one Instagram post" in prompt:
        if os.environ.get("FAKE_CLAUDE_DESCRIBE_FAIL") == "1":
            print("error: no model", file=sys.stderr)
            return 1
        print('## On screen\n- "Comment SITES for the list"')
        return 0
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
