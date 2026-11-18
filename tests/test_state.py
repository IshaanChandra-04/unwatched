from pathlib import Path

from unwatched.state import load_state, save_state


def test_state_defaults_and_roundtrip(tmp_path):
    state = load_state(tmp_path)
    assert state == {
        "last_run": None,
        "last_digest": None,
        "last_error": None,
        "last_summary": None,
        "digested": {},
    }
    state["last_run"] = "2026-11-14T15:00:00Z"
    save_state(tmp_path, state)
    assert load_state(tmp_path)["last_run"] == "2026-11-14T15:00:00Z"


def test_save_state_writes_whole_files_only(tmp_path, monkeypatch):
    import os

    replaced = []
    real = os.replace
    monkeypatch.setattr(os, "replace", lambda a, b: replaced.append(Path(a).name) or real(a, b))
    save_state(tmp_path, load_state(tmp_path) | {"last_run": "x"})
    assert replaced == ["state.json.tmp"] and load_state(tmp_path)["last_run"] == "x"
