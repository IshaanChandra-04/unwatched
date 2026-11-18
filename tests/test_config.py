from pathlib import Path

import pytest

from unwatched.config import load_config


def test_defaults_when_no_file():
    cfg = load_config(None)
    assert cfg["fetch"] == {"kinds": ["saved", "dm"], "max": 300, "delay": 3}
    assert cfg["digest"] is False and cfg["digest_max_turns"] == 60
    assert cfg["claude"] == "claude"
    assert cfg["frames"] is True and cfg["digest_max_posts"] == 40
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


def test_tilde_expands_to_the_home_folder(tmp_path):
    (tmp_path / "u.toml").write_text(
        'work = "~/uw"\nprofile = "~/p.md"\nmaster = "~/m.md"\n'
        '[sources]\nlinks = ["~/l.md"]\nexport = ["~/e.zip"]\n',
        encoding="utf-8",
    )
    cfg = load_config(tmp_path / "u.toml")
    home = Path.home()
    assert cfg["work"] == str(home / "uw")
    assert cfg["profile"] == str(home / "p.md") and cfg["master"] == str(home / "m.md")
    assert cfg["sources"]["links"] == [str(home / "l.md")]
    assert cfg["sources"]["export"] == [str(home / "e.zip")]


def test_unknown_keys_and_wrong_types_are_rejected(tmp_path):
    (tmp_path / "u.toml").write_text("digest_max_turn = 100\n", encoding="utf-8")
    with pytest.raises(ValueError, match="digest_max_turn"):
        load_config(tmp_path / "u.toml")
    (tmp_path / "u.toml").write_text('[sources]\ndm = "https://x/"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="sources.dm must be a list"):
        load_config(tmp_path / "u.toml")
    (tmp_path / "u.toml").write_text("[fetches]\nmax = 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="fetches"):
        load_config(tmp_path / "u.toml")


def test_a_bundled_profile_name_resolves_to_the_shipped_file(tmp_path):
    (tmp_path / "u.toml").write_text('profile = "tech"\n', encoding="utf-8")
    cfg = load_config(tmp_path / "u.toml")
    assert cfg["profile"].endswith("tech.md") and Path(cfg["profile"]).is_file()
    assert "Keep" in Path(cfg["profile"]).read_text(encoding="utf-8")
