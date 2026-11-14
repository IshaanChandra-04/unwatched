from unwatched.config import load_config


def test_defaults_when_no_file():
    cfg = load_config(None)
    assert cfg["fetch"] == {"kinds": ["saved", "dm"], "max": 300, "delay": 3}
    assert cfg["digest"] is False and cfg["digest_max_turns"] == 60
    assert cfg["transcribe"]["model"] == "small"


def test_example_config_parses_and_resolves_paths(tmp_path):
    (tmp_path / "unwatched.toml").write_text(
        'work = "w"\n'
        'profile = "profiles/tech.md"\n'
        "digest = true\n"
        "[sources]\n"
        'dm = ["https://www.instagram.com/direct/t/1/"]\n'
        "saved = true\n"
        "[fetch]\n"
        'kinds = ["saved", "dm"]\n'
        "max = 50\n",
        encoding="utf-8",
    )
    cfg = load_config(tmp_path / "unwatched.toml")
    assert cfg["work"] == str(tmp_path / "w")
    assert cfg["profile"] == str(tmp_path / "profiles" / "tech.md")
    assert cfg["digest"] is True
    assert cfg["fetch"]["max"] == 50 and cfg["fetch"]["delay"] == 3
    assert cfg["sources"]["dm"] == ["https://www.instagram.com/direct/t/1/"]
    assert cfg["sources"]["saved"] is True
