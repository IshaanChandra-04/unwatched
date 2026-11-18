import base64
import time
from contextlib import contextmanager
from pathlib import Path

import pytest

from unwatched import browser
from unwatched.browser import _is_blocked, codes_from_srcs, login, sweep_dm, sweep_grid
from unwatched.shortcode import media_id_to_shortcode

FIX = Path(__file__).parent / "fixtures"
ALL = [media_id_to_shortcode(3700000000000000000 + i) for i in range(59, -1, -1)]
GRID = [media_id_to_shortcode(3800000000000000000 + i) for i in range(44, -1, -1)]
LAZY = [media_id_to_shortcode(3800000000000000000 + i) for i in range(59, -1, -1)]


def test_blocked_pages_are_login_or_challenge():
    assert _is_blocked("https://www.instagram.com/accounts/login/?next=%2Fdirect%2F")
    assert _is_blocked("https://www.instagram.com/challenge/action/AXk/")
    assert not _is_blocked("https://www.instagram.com/direct/t/1/")


@pytest.mark.browser
def test_sweep_grid_keeps_going_past_tiles_it_already_collected(tmp_path):
    url = (FIX / "saved_grid_lazy.html").resolve().as_uri()
    found = sweep_grid(url, set(), "saved", profile_dir=tmp_path, headless=True, wait_ms=60)
    assert [c for c, _, _ in found] == LAZY


@pytest.mark.browser
def test_sweep_grid_scrolls_to_the_end_and_stops_at_known(tmp_path):
    url = (FIX / "saved_grid.html").resolve().as_uri()
    found = sweep_grid(url, set(), "saved", profile_dir=tmp_path, headless=True, wait_ms=50)
    assert [c for c, _, _ in found] == GRID
    assert found[0][1] == {"kind": "saved", "name": "saved", "via": "live", "ts": found[0][1]["ts"]}
    found = sweep_grid(url, set(GRID[6:]), "saved", profile_dir=tmp_path, headless=True, wait_ms=50)
    assert [c for c, _, _ in found] == GRID[:6]


def test_codes_from_srcs_is_pure():
    key = base64.b64encode(b"3700000000000000000_1").decode()
    src = f"https://cdn/x.jpg?stp=1&ig_cache_key={key}&_nc=1"
    assert codes_from_srcs([src, src]) == [media_id_to_shortcode(3700000000000000000)]


@pytest.mark.browser
def test_sweep_dm_full_collects_everything(tmp_path):
    url = (FIX / "dm_thread.html").resolve().as_uri()
    found = sweep_dm(url, set(), profile_dir=tmp_path, full=True, headless=True, wait_ms=50)
    assert [c for c, _, _ in found] == ALL
    assert found[0][1]["kind"] == "dm" and found[0][1]["via"] == "live"
    assert found[0][1]["name"] == "kungfookah"


@pytest.mark.browser
def test_sweep_dm_waits_for_content_that_loads_late(tmp_path):
    url = (FIX / "dm_thread_delayed.html").resolve().as_uri()
    found = sweep_dm(url, set(), profile_dir=tmp_path, full=True, headless=True, wait_ms=50)
    assert [c for c, _, _ in found] == ALL
    assert found[0][1]["name"] == "kungfookah"  # read after the list exists, not from the sidebar


@pytest.mark.browser
def test_sweep_dm_stops_after_known_streak(tmp_path):
    url = (FIX / "dm_thread.html").resolve().as_uri()
    known = set(ALL[5:])
    found = sweep_dm(url, known, profile_dir=tmp_path, headless=True, wait_ms=50)
    codes = [c for c, _, _ in found]
    assert codes[:5] == ALL[:5] and len(codes) < 40


@pytest.mark.browser
def test_sweep_dm_without_a_header_is_named_after_the_last_url_segment(tmp_path):
    page = tmp_path / "mythread.html"  # no trailing slash, like a pasted thread URL
    page.write_text(
        '<!DOCTYPE html><a href="https://www.instagram.com/p/AAAAAAAAAAA/">x</a>', encoding="utf-8"
    )
    found = sweep_dm(
        page.as_uri(), set(), profile_dir=tmp_path / "profile", headless=True, wait_ms=50
    )
    assert [c for c, _, _ in found] == ["AAAAAAAAAAA"]
    assert found[0][1]["name"] == "mythreadhtml"  # the fallback keeps word characters only


def test_login_needs_a_session_cookie_on_a_page_that_is_not_blocked(tmp_path, monkeypatch):
    class Page:
        url = "https://www.instagram.com/accounts/login/"

        def goto(self, url):
            pass

    class Ctx:
        pages = [Page()]

        def cookies(self):
            return [{"name": "sessionid", "domain": ".instagram.com"}]

    @contextmanager
    def fake_context(profile_dir, headless):
        yield Ctx()

    monkeypatch.setattr(browser, "_context", fake_context)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    assert login(profile_dir=tmp_path, timeout_s=0.01) is False
    Page.url = "https://www.instagram.com/"
    assert login(profile_dir=tmp_path, timeout_s=0.01) is True


@contextmanager
def _serve(root: Path):
    import threading
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    handler = partial(SimpleHTTPRequestHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()


@pytest.mark.browser
def test_fetch_pictures_walks_the_carousel_and_reads_the_caption(tmp_path):
    import json

    from unwatched.browser import fetch_pictures

    (tmp_path / "frames" / "AAAAAAAAAAA").mkdir(parents=True)
    (tmp_path / "frames" / "AAAAAAAAAAA" / "01.jpg").write_bytes(b"cover")  # replaced
    with _serve(FIX / "post") as base:
        counts = fetch_pictures(
            tmp_path,
            ["AAAAAAAAAAA", "BBBBBBBBBBB"],
            profile_dir=tmp_path / "profile",
            headless=True,
            wait_ms=50,
            base_url=base,
        )
    assert counts == {"fetched": 1, "failed": 1}
    names = sorted(p.name for p in (tmp_path / "frames" / "AAAAAAAAAAA").iterdir())
    assert names == ["01.jpg", "02.jpg"]
    assert (tmp_path / "frames" / "AAAAAAAAAAA" / "01.jpg").read_bytes() != b"cover"
    meta = json.loads((tmp_path / "meta" / "AAAAAAAAAAA.json").read_text(encoding="utf-8"))
    assert meta["caption"].startswith("Top 30 skills") and meta["slides"] == 2
    failed = json.loads((tmp_path / "meta" / "BBBBBBBBBBB.json").read_text(encoding="utf-8"))
    assert failed["pictures_retries"] == 1 and "no pictures" in failed["pictures_error"]
