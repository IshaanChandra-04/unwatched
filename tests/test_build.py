from unwatched.build import render

POSTS = {
    "AAAAAAAAAAA": {
        "code": "AAAAAAAAAAA",
        "url": "https://www.instagram.com/p/AAAAAAAAAAA/",
        "first_seen": "2025-10-31T08:40:00Z",
        "local_media": None,
        "sources": [
            {"kind": "saved", "name": "saved", "via": "export", "ts": "2025-10-31T08:40:00Z"},
            {"kind": "dm", "name": "kungfookah", "via": "live", "ts": None, "text": "café tips"},
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
        "| saved: saved; dm: kungfookah |"
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
