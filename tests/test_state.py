from unwatched.state import load_state, save_state


def test_state_defaults_and_roundtrip(tmp_path):
    state = load_state(tmp_path)
    assert state == {
        "last_run": None,
        "last_digest": None,
        "last_error": None,
        "last_summary": None,
    }
    state["last_run"] = "2026-11-14T15:00:00Z"
    save_state(tmp_path, state)
    assert load_state(tmp_path)["last_run"] == "2026-11-14T15:00:00Z"
