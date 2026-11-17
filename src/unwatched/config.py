"""Load ``unwatched.toml`` over the defaults.

Relative paths resolve from the file's folder; ``~`` is the home folder.
"""

import copy
import tomllib
from pathlib import Path

DEFAULTS = {
    "work": "work",
    "profile": None,
    "master": None,
    "digest": False,
    "digest_max_turns": 60,
    "username": None,
    "sources": {"dm": [], "saved": False, "links": [], "export": []},
    "fetch": {"kinds": ["saved", "dm"], "max": 300, "delay": 3},
    "transcribe": {"model": "small", "language": "en"},
}


def load_config(path: Path | None) -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    if path is None:
        return cfg
    path = Path(path).absolute()
    for key, value in tomllib.loads(path.read_text(encoding="utf-8")).items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            cfg[key].update(value)
        else:
            cfg[key] = value
    base = path.parent

    def resolve(p: str) -> str:
        return str(base / Path(p).expanduser())

    for key in ("work", "profile", "master"):
        if cfg[key]:
            cfg[key] = resolve(cfg[key])
    for key in ("links", "export"):
        cfg["sources"][key] = [resolve(p) for p in cfg["sources"][key]]
    return cfg
