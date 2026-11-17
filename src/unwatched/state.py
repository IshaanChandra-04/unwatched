"""Run state in ``work/state.json``: when things last happened and what went wrong."""

import json
from pathlib import Path

_DEFAULTS = {"last_run": None, "last_digest": None, "last_error": None, "last_summary": None}


def load_state(work: Path) -> dict:
    path = work / "state.json"
    state = dict(_DEFAULTS) | {"digested": {}}  # code -> materials the digest has seen
    if path.exists():
        state.update(json.loads(path.read_text(encoding="utf-8")))
    return state


def save_state(work: Path, state: dict) -> None:
    work.mkdir(parents=True, exist_ok=True)
    (work / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
