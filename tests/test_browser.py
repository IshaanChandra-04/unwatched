import base64
from pathlib import Path

import pytest

from unwatched.browser import _is_blocked, codes_from_srcs, sweep_dm, sweep_grid
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
