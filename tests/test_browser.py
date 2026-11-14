import base64
from pathlib import Path

import pytest

from unwatched.browser import codes_from_srcs, sweep_dm
from unwatched.shortcode import media_id_to_shortcode

FIX = Path(__file__).parent / "fixtures"
ALL = [media_id_to_shortcode(3700000000000000000 + i) for i in range(59, -1, -1)]


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
def test_sweep_dm_stops_after_known_streak(tmp_path):
    url = (FIX / "dm_thread.html").resolve().as_uri()
    known = set(ALL[5:])
    found = sweep_dm(url, known, profile_dir=tmp_path, headless=True, wait_ms=50)
    codes = [c for c, _, _ in found]
    assert codes[:5] == ALL[:5] and len(codes) < 40
