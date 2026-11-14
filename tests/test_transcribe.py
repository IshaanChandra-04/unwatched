from unwatched.posts import add_source
from unwatched.transcribe import audio_path, todo

SRC = {"kind": "dm", "name": "t", "via": "live", "ts": None}


def test_todo_skips_done_and_forces_only(tmp_path):
    posts = {}
    for code in ("AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC"):
        add_source(posts, code, SRC)
    (tmp_path / "audio").mkdir()
    (tmp_path / "transcripts").mkdir()
    (tmp_path / "audio" / "AAAAAAAAAAA.m4a").touch()
    (tmp_path / "audio" / "BBBBBBBBBBB.m4a").touch()
    (tmp_path / "transcripts" / "BBBBBBBBBBB.txt").write_text("done", encoding="utf-8")
    assert todo(tmp_path, posts, None) == ["AAAAAAAAAAA"]
    assert todo(tmp_path, posts, {"BBBBBBBBBBB", "CCCCCCCCCCC"}) == ["BBBBBBBBBBB"]
    assert audio_path(tmp_path, "CCCCCCCCCCC", posts) is None


def test_audio_path_prefers_local_media_for_archived(tmp_path):
    posts = {
        "archived-1": {
            "code": "archived-1",
            "url": None,
            "sources": [],
            "first_seen": "x",
            "local_media": str(tmp_path / "v.mp4"),
        }
    }
    (tmp_path / "v.mp4").touch()
    assert audio_path(tmp_path, "archived-1", posts) == tmp_path / "v.mp4"
