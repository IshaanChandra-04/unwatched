import json
import sys
from pathlib import Path

import unwatched.fetch as fetch_module
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


VIDEO_JSON = json.dumps({"uploader": "u", "description": "d", "duration": 10})
IMAGE_JSON = json.dumps({"uploader": "u", "description": "d"})
URL_A = "https://www.instagram.com/p/AAAAAAAAAAA/"
URL_D = "https://www.instagram.com/p/DZdoibdDSu2/"


def test_fetch_one_video_downloads_audio_and_video(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_YTDLP_JSON", VIDEO_JSON)
    meta = fetch_one("AAAAAAAAAAA", URL_A, tmp_path, None, ytdlp=FAKE)
    assert meta["error"] is None
    assert list((tmp_path / "audio").glob("AAAAAAAAAAA.*"))
    assert [p.name for p in (tmp_path / "video").glob("AAAAAAAAAAA.*")] == ["AAAAAAAAAAA.mp4"]


def test_fetch_one_image_downloads_thumbnails_into_frames(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_YTDLP_JSON", IMAGE_JSON)
    monkeypatch.setenv("FAKE_YTDLP_CAROUSEL", "1")
    meta = fetch_one("DZdoibdDSu2", URL_D, tmp_path, None, ytdlp=FAKE)
    assert meta["media_type"] == "image" and meta["error"] is None
    names = sorted(p.name for p in (tmp_path / "frames" / "DZdoibdDSu2").iterdir())
    assert names == ["01.jpg", "02.jpg"]


def test_fetch_one_skips_downloads_that_already_exist(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_YTDLP_JSON", VIDEO_JSON)
    monkeypatch.setenv("FAKE_YTDLP_LOG", str(tmp_path / "calls.jsonl"))
    for folder, name in (("audio", "AAAAAAAAAAA.m4a"), ("video", "AAAAAAAAAAA.mp4")):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / name).write_bytes(b"x")
    fetch_one("AAAAAAAAAAA", URL_A, tmp_path, None, ytdlp=FAKE)
    calls = (tmp_path / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(calls) == 1 and "--dump-single-json" in calls[0]


def test_fetch_one_image_thumbnail_failure_is_recorded(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_YTDLP_JSON", IMAGE_JSON)
    monkeypatch.setenv("FAKE_YTDLP_FAIL_THUMBNAIL", "1")
    meta = fetch_one("DZdoibdDSu2", URL_D, tmp_path, None, ytdlp=FAKE)
    assert "thumbnail" in meta["error"] and meta["retries"] == 1


def test_fetch_one_times_out_a_stalled_download(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_YTDLP_JSON", VIDEO_JSON)
    monkeypatch.setenv("FAKE_YTDLP_SLEEP", "3")
    monkeypatch.setattr(fetch_module, "TIMEOUT_S", 0.3)
    meta = fetch_one("AAAAAAAAAAA", URL_A, tmp_path, None, ytdlp=FAKE)
    assert "timed out" in meta["error"] and meta["retries"] == 1


def _meta(tmp_path, code, **fields):
    (tmp_path / "meta").mkdir(exist_ok=True)
    (tmp_path / "meta" / f"{code}.json").write_text(
        json.dumps({"code": code, "error": None} | fields), encoding="utf-8"
    )


def test_pending_includes_posts_missing_their_media(tmp_path):
    _meta(tmp_path, "AAAAAAAAAAA", media_type="video")
    _meta(tmp_path, "BBBBBBBBBBB", media_type="video")
    (tmp_path / "video").mkdir()
    (tmp_path / "video" / "BBBBBBBBBBB.mp4").write_bytes(b"x")
    _meta(tmp_path, "CCCCCCCCCCC", media_type="image")
    _meta(tmp_path, "DDDDDDDDDDD", media_type="image")
    (tmp_path / "frames" / "DDDDDDDDDDD").mkdir(parents=True)
    (tmp_path / "frames" / "DDDDDDDDDDD" / "01.jpg").write_bytes(b"x")
    codes = ["AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC", "DDDDDDDDDDD"]
    assert pending(tmp_path, codes) == ["AAAAAAAAAAA", "CCCCCCCCCCC"]


def test_number_pictures_converts_webp_covers_and_renumbers(tmp_path):
    from PIL import Image

    from unwatched.fetch import number_pictures, pictures

    folder = tmp_path / "frames" / "AAAAAAAAAAA"
    folder.mkdir(parents=True)
    Image.new("RGB", (8, 8), "red").save(folder / "1.webp")
    (folder / "2.jpg").write_bytes(b"x")
    number_pictures(folder)
    assert [p.name for p in pictures(tmp_path, "AAAAAAAAAAA")] == ["01.jpg", "02.jpg"]


def test_pictures_todo_selects_image_posts_without_slides(tmp_path):
    from unwatched.fetch import pictures_todo

    _meta(tmp_path, "AAAAAAAAAAA", media_type="image")
    _meta(tmp_path, "BBBBBBBBBBB", media_type="image", slides=3)
    _meta(tmp_path, "CCCCCCCCCCC", media_type="video")
    _meta(tmp_path, "DDDDDDDDDDD", media_type="image", pictures_retries=3)
    _meta(tmp_path, "EEEEEEEEEEE", media_type="image", pictures_retries=2)
    posts = {
        c: {} for c in ["AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC", "DDDDDDDDDDD", "EEEEEEEEEEE"]
    }
    assert pictures_todo(tmp_path, posts) == ["AAAAAAAAAAA", "EEEEEEEEEEE"]
