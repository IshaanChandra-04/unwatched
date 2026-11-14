import json
import sys
from pathlib import Path

from unwatched.fetch import DEFAULT_YTDLP, fetch_one, pending, select, trim_meta
from unwatched.posts import add_source

FAKE = [sys.executable, str(Path(__file__).parent / "fake_ytdlp.py")]


def _src(kind, name, via, day):
    return {"kind": kind, "name": name, "via": via, "ts": f"2025-{day}T00:00:00Z"}


def _posts():
    p = {}
    add_source(p, "AAAAAAAAAAA", _src("saved", "saved", "export", "10-31"))
    add_source(p, "BBBBBBBBBBB", _src("dm", "kungfookah", "live", "11-01"))
    add_source(p, "CCCCCCCCCCC", _src("liked", "likes", "export", "11-02"))
    add_source(p, "DDDDDDDDDDD", _src("dm", "other", "live", "11-03"))
    return p


def test_select_by_kind_thread_since_and_only():
    p = _posts()
    assert select(p, {"saved", "dm"}, None, None, None) == [
        "AAAAAAAAAAA",
        "BBBBBBBBBBB",
        "DDDDDDDDDDD",
    ]
    assert select(p, {"dm"}, {"kungfookah"}, None, None) == ["BBBBBBBBBBB"]
    assert select(p, {"saved", "dm"}, None, "2025-11-02T00:00:00Z", None) == ["DDDDDDDDDDD"]
    assert select(p, {"saved"}, None, None, {"CCCCCCCCCCC"}) == ["CCCCCCCCCCC"]


def test_trim_meta_video_image_and_carousel():
    video = {"uploader": "u", "description": "d", "upload_date": "20251031", "duration": 42.0}
    assert trim_meta("A", video)["media_type"] == "video"
    assert trim_meta("A", {"uploader": "u", "description": "d"})["media_type"] == "image"
    carousel = {
        "_type": "playlist",
        "uploader": "u",
        "description": "d",
        "entries": [{"duration": None}, {"duration": 12.5}],
    }
    car = trim_meta("A", carousel)
    assert car["media_type"] == "video" and car["duration"] == 12.5
    assert trim_meta("A", {"_type": "playlist", "entries": [{}, {}]})["media_type"] == "image"


def test_fetch_one_video_downloads_audio(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "FAKE_YTDLP_JSON", json.dumps({"uploader": "u", "description": "d", "duration": 10})
    )
    meta = fetch_one(
        "AAAAAAAAAAA", "https://www.instagram.com/p/AAAAAAAAAAA/", tmp_path, None, ytdlp=FAKE
    )
    assert meta["media_type"] == "video" and meta["error"] is None
    assert list((tmp_path / "audio").glob("AAAAAAAAAAA.*"))
    assert (tmp_path / "meta" / "AAAAAAAAAAA.json").exists()


def test_pending_retries_failed_posts_and_skips_done(tmp_path):
    (tmp_path / "meta").mkdir()
    (tmp_path / "meta" / "AAAAAAAAAAA.json").write_text('{"error": null}', encoding="utf-8")
    (tmp_path / "meta" / "BBBBBBBBBBB.json").write_text(
        '{"error": "login required"}', encoding="utf-8"
    )
    assert pending(tmp_path, ["AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC"]) == [
        "BBBBBBBBBBB",
        "CCCCCCCCCCC",
    ]


def test_default_ytdlp_is_the_installed_module_not_a_path_lookup():
    assert DEFAULT_YTDLP == [sys.executable, "-m", "yt_dlp"]


def test_fetch_one_keeps_the_caption_of_an_image_post(tmp_path, monkeypatch):
    # yt-dlp refuses image posts unless told to ignore the missing formats
    monkeypatch.setenv("FAKE_YTDLP_REQUIRE_IGNORE", "1")
    monkeypatch.setenv(
        "FAKE_YTDLP_JSON", json.dumps({"uploader": "u", "description": "carousel caption"})
    )
    meta = fetch_one(
        "DZdoibdDSu2", "https://www.instagram.com/p/DZdoibdDSu2/", tmp_path, None, ytdlp=FAKE
    )
    assert meta["media_type"] == "image" and meta["error"] is None
    assert meta["caption"] == "carousel caption" and meta["uploader"] == "u"
    assert not (tmp_path / "audio").exists()


def test_fetch_one_failure_is_recorded_not_raised(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_YTDLP_FAIL", "1")
    meta = fetch_one(
        "BBBBBBBBBBB", "https://www.instagram.com/p/BBBBBBBBBBB/", tmp_path, None, ytdlp=FAKE
    )
    assert "login required" in meta["error"]


def test_pending_gives_up_after_three_failed_fetches(tmp_path):
    (tmp_path / "meta").mkdir()
    (tmp_path / "meta" / "AAAAAAAAAAA.json").write_text(
        '{"error": "private", "retries": 2}', encoding="utf-8"
    )
    (tmp_path / "meta" / "BBBBBBBBBBB.json").write_text(
        '{"error": "private", "retries": 3}', encoding="utf-8"
    )
    assert pending(tmp_path, ["AAAAAAAAAAA", "BBBBBBBBBBB"]) == ["AAAAAAAAAAA"]


def test_fetch_one_counts_failed_attempts(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_YTDLP_FAIL", "1")
    url = "https://www.instagram.com/p/BBBBBBBBBBB/"
    fetch_one("BBBBBBBBBBB", url, tmp_path, None, ytdlp=FAKE)
    meta = fetch_one("BBBBBBBBBBB", url, tmp_path, None, ytdlp=FAKE)
    assert meta["retries"] == 2
