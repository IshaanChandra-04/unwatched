"""A stand-in for `claude -p` used by the tests. Behaviour is driven by environment variables."""

import os
import sys
from pathlib import Path


def main() -> int:
    if os.environ.get("FAKE_CLAUDE_SILENT") == "1":
        return 0
    master = Path(os.environ["FAKE_MASTER"])
    with master.open("a", encoding="utf-8") as f:
        f.write("digested\n")
    print("UNWATCHED_DIGEST_DONE kept=2 total=5")
    return 0


if __name__ == "__main__":
    sys.exit(main())
