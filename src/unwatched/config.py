"""Load ``unwatched.toml`` over the defaults.

Relative paths resolve from the file's folder; ``~`` is the home folder; a profile named
``tech`` (or any other bundled name) is the one shipped with the package. Unknown keys and
values of the wrong type are refused, so a typo cannot silently fall back to a default.
"""

import copy
import tomllib
from importlib import resources
from pathlib import Path

DEFAULTS = {
    "work": "work",
    "profile": None,
    "master": None,
    "digest": False,
    "digest_max_turns": 60,
    "digest_max_posts": 40,
    "claude": "claude",
    "frames": True,
    "username": None,
    "sources": {"dm": [], "saved": False, "links": [], "export": []},
    "fetch": {"kinds": ["saved", "dm"], "max": 300, "delay": 3},
    "transcribe": {"model": "small", "language": "en"},
}
_KINDS = {
    bool: "true or false",
    int: "a number",
    float: "a number",
    str: "a string",
    list: "a list",
}


def _check(given: dict, defaults: dict, prefix: str = "") -> None:
    for key, value in given.items():
        name = prefix + key
        if key not in defaults:
            raise ValueError(f"unwatched.toml: unknown key {name}")
        want = defaults[key]
        if isinstance(want, dict):
            if not isinstance(value, dict):
                raise ValueError(f"unwatched.toml: {name} must be a table")
            _check(value, want, name + ".")
            continue
        expected = str if want is None else type(want)
        if expected in (int, float):
            ok = isinstance(value, int | float) and not isinstance(value, bool)
        else:
            ok = isinstance(value, expected)
        if not ok:
            raise ValueError(f"unwatched.toml: {name} must be {_KINDS[expected]}")


def bundled_profile(name: str) -> Path | None:
    """The profile shipped with the package under that name, if there is one."""
    packaged = resources.files("unwatched") / "profiles" / f"{name}.md"
    if packaged.is_file():
        return Path(str(packaged))
    repo_copy = Path(__file__).resolve().parents[2] / "profiles" / f"{name}.md"
    return repo_copy if repo_copy.is_file() else None


def load_config(path: Path | None) -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    if path is None:
        return cfg
    path = Path(path).absolute()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    _check(data, DEFAULTS)
    for key, value in data.items():
        if isinstance(value, dict):
            cfg[key].update(value)
        else:
            cfg[key] = value
    base = path.parent

    def resolve(p: str) -> str:
        return str(base / Path(p).expanduser())

    if cfg["profile"] and not Path(resolve(cfg["profile"])).exists():
        if bundled := bundled_profile(cfg["profile"]):
            cfg["profile"] = str(bundled)
    for key in ("work", "profile", "master"):
        if cfg[key]:
            cfg[key] = resolve(cfg[key])
    for key in ("links", "export"):
        cfg["sources"][key] = [resolve(p) for p in cfg["sources"][key]]
    return cfg
