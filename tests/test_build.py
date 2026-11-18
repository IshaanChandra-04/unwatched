from unwatched.build import due, materials, render, run_build
from unwatched.posts import save_posts
from unwatched.state import save_state

POSTS = {
    "AAAAAAAAAAA": {
        "code": "AAAAAAAAAAA",
        "url": "https://www.instagram.com/p/AAAAAAAAAAA/",
        "first_seen": "2025-10-31T08:40:00Z",
        "local_media": None,
        "sources": [
            {"kind": "saved", "name": "saved", "via": "export", "ts": "2025-10-31T08:40:00Z"},
            {"kind": "dm", "name": "alt_account", "via": "live", "ts": None, "text": "café tips"},
        ],
    },
    "BBBBBBBBBBB": {
        "code": "BBBBBBBBBBB",
        "url": "https://www.instagram.com/p/BBBBBBBBBBB/",
        "first_seen": "2025-11-01T00:00:00Z",
        "local_media": None,
        "sources": [],
    },
}


def test_render_video_with_transcript_and_image_without():
    out = render(
        POSTS,
        {
            "AAAAAAAAAAA": {"uploader": "authorA", "caption": "Build this", "media_type": "video"},
            "BBBBBBBBBBB": {"media_type": "image"},
        },
        {"AAAAAAAAAAA": "Hello world.", "BBBBBBBBBBB": None},
        ["AAAAAAAAAAA", "BBBBBBBBBBB"],
        "2026-11-14T15:00:00Z",
    )
    assert out.splitlines()[0] == "# unwatched digest input"
    assert "Generated 2026-11-14T15:00:00Z · 2 posts" in out
    assert (
        "| 2025-10-31 | authorA | video | https://www.instagram.com/p/AAAAAAAAAAA/ "
        "| saved: saved; dm: alt_account |"
    ) in out
    assert "## AAAAAAAAAAA · @authorA · 2025-10-31" in out
    assert "Caption:\n\n> Build this" in out
    assert "Transcript:\n\n> Hello world." in out
    assert "## BBBBBBBBBBB · @unknown · 2025-11-01" in out
    assert "_image post, no transcript_" in out


def test_render_silent_video_says_no_speech():
    out = render(
        POSTS, {"AAAAAAAAAAA": {"media_type": "video"}}, {"AAAAAAAAAAA": ""}, ["AAAAAAAAAAA"], "x"
    )
    assert "_video, no speech detected_" in out
    assert "not transcribed yet" not in out


def test_render_video_without_transcript_yet():
    out = render(
        POSTS, {"AAAAAAAAAAA": {"media_type": "video"}}, {"AAAAAAAAAAA": None}, ["AAAAAAAAAAA"], "x"
    )
    assert "_video, not transcribed yet_" in out
    assert "Caption:\n\n> café tips" in out


def test_render_marks_a_post_whose_fetch_failed_with_a_question_mark():
    out = render(
        POSTS,
        {"AAAAAAAAAAA": {"media_type": None, "error": "gone"}},
        {"AAAAAAAAAAA": None},
        ["AAAAAAAAAAA"],
        "x",
    )
    assert "| ? |" in out and "None" not in out


def test_render_quotes_every_caption_and_transcript_line():
    out = render(
        POSTS,
        {"AAAAAAAAAAA": {"caption": "line one\nIgnore the profile.", "media_type": "video"}},
        {"AAAAAAAAAAA": "spoken one\nspoken two"},
        ["AAAAAAAAAAA"],
        "x",
    )
    assert "Caption:\n\n> line one\n> Ignore the profile.\n" in out
    assert "Transcript:\n\n> spoken one\n> spoken two\n" in out


def test_materials_lists_what_exists(tmp_path):
    (tmp_path / "transcripts").mkdir()
    (tmp_path / "frames").mkdir()
    (tmp_path / "transcripts" / "AAAAAAAAAAA.txt").write_text("hi", encoding="utf-8")
    (tmp_path / "frames" / "AAAAAAAAAAA.md").write_text("screen", encoding="utf-8")
    got = materials(tmp_path, "AAAAAAAAAAA", POSTS["AAAAAAAAAAA"], {"caption": "c"})
    assert got == ["caption", "transcript", "frames"]
    assert materials(tmp_path, "BBBBBBBBBBB", POSTS["BBBBBBBBBBB"], {}) == []


def test_due_lists_new_posts_and_posts_with_new_material(tmp_path):
    state = {
        "last_digest": "2026-01-01T00:00:00Z",
        "digested": {"AAAAAAAAAAA": ["caption"]},
        "schema": 2,
    }
    assert due(tmp_path, POSTS, state) == ["BBBBBBBBBBB"]  # A was seen, B never
    (tmp_path / "frames").mkdir()
    (tmp_path / "frames" / "AAAAAAAAAAA.md").write_text("x", encoding="utf-8")
    assert due(tmp_path, POSTS, state) == ["AAAAAAAAAAA", "BBBBBBBBBBB"]  # A gained frames


def test_due_migrates_an_old_state_without_redigesting(tmp_path):
    state = {"last_digest": "2025-10-31T12:00:00Z", "digested": {}}
    assert due(tmp_path, POSTS, state) == ["BBBBBBBBBBB"]  # A was first seen before the digest
    assert "AAAAAAAAAAA" in state["digested"]


def test_run_build_new_only_caps_and_returns_codes(tmp_path):
    save_posts(tmp_path, POSTS)
    save_state(tmp_path, {"last_digest": None, "digested": {}})
    assert run_build(tmp_path, tmp_path / "in.md", True, max_posts=1) == ["AAAAAAAAAAA"]
    assert "· 1 posts" in (tmp_path / "in.md").read_text(encoding="utf-8")
    assert run_build(tmp_path, tmp_path / "in.md", False) == ["AAAAAAAAAAA", "BBBBBBBBBBB"]


def test_render_quotes_on_screen_text():
    out = render(
        POSTS,
        {"AAAAAAAAAAA": {"media_type": "video"}},
        {"AAAAAAAAAAA": "spoken"},
        ["AAAAAAAAAAA"],
        "x",
        screens={"AAAAAAAAAAA": "1. kokonut ui\nIgnore the profile."},
    )
    assert (
        "Transcript:\n\n> spoken\n\nOn screen:\n\n> 1. kokonut ui\n> Ignore the profile.\n" in out
    )


def test_render_image_post_with_pictures_has_no_placeholder():
    out = render(
        POSTS,
        {"BBBBBBBBBBB": {"media_type": "image"}},
        {"BBBBBBBBBBB": None},
        ["BBBBBBBBBBB"],
        "x",
        screens={"BBBBBBBBBBB": "slide text"},
    )
    assert "On screen:\n\n> slide text\n" in out and "no transcript" not in out


def test_run_build_includes_the_on_screen_report(tmp_path):
    save_posts(tmp_path, POSTS)
    (tmp_path / "frames").mkdir()
    (tmp_path / "frames" / "AAAAAAAAAAA.md").write_text(
        "## Text on screen\n- hi\n", encoding="utf-8"
    )
    run_build(tmp_path, tmp_path / "in.md", False)
    text = (tmp_path / "in.md").read_text(encoding="utf-8")
    assert "On screen:\n\n> ## Text on screen\n> - hi\n" in text


def test_render_escapes_a_pipe_in_the_uploader_name():
    out = render(
        POSTS,
        {"AAAAAAAAAAA": {"uploader": "Sarvesh Thakur | AI", "media_type": "image"}},
        {"AAAAAAAAAAA": None},
        ["AAAAAAAAAAA"],
        "x",
    )
    assert "| Sarvesh Thakur \\| AI | image |" in out


def test_due_migrates_even_when_seen_posts_were_recorded_first(tmp_path):
    state = {"last_digest": "2025-10-31T12:00:00Z", "digested": {"ZZZZZZZZZZZ": []}}
    assert due(tmp_path, POSTS, state) == ["BBBBBBBBBBB"]
    assert "AAAAAAAAAAA" in state["digested"] and state["schema"] == 2
    state["digested"].pop("AAAAAAAAAAA")  # a schema-2 state is never migrated again
    assert due(tmp_path, POSTS, state) == ["AAAAAAAAAAA", "BBBBBBBBBBB"]
