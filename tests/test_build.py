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
    assert "Caption: Build this" in out
    assert "Transcript:\n\nHello world." in out
    assert "## BBBBBBBBBBB · @unknown · 2025-11-01" in out
    assert "_image post, no transcript_" in out


def test_render_video_without_transcript_yet():
    out = render(
        POSTS, {"AAAAAAAAAAA": {"media_type": "video"}}, {"AAAAAAAAAAA": None}, ["AAAAAAAAAAA"], "x"
    )
    assert "_video, not transcribed yet_" in out
    assert "Caption: café tips" in out
