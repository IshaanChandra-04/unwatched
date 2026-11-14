import base64
from urllib.parse import quote

from unwatched.shortcode import (
    ALPHABET,
    codes_from_text,
    media_id_to_shortcode,
    shortcode_from_cache_key,
    url_for,
)


def test_alphabet_is_instagram_order():
    assert len(ALPHABET) == 64
    assert ALPHABET[0] == "A" and ALPHABET[26] == "a" and ALPHABET[52] == "0"
    assert ALPHABET[62:] == "-_"


def test_media_id_to_shortcode_small_values():
    assert media_id_to_shortcode(0) == "A"
    assert media_id_to_shortcode(63) == "_"
    assert media_id_to_shortcode(64) == "BA"


def test_cache_key_decodes_to_shortcode():
    key = quote(base64.b64encode(b"3700000000000000000_123").decode())
    assert shortcode_from_cache_key(key) == media_id_to_shortcode(3700000000000000000)


def test_cache_key_garbage_is_none():
    assert shortcode_from_cache_key("not-base64!!") is None
    assert shortcode_from_cache_key(base64.b64encode(b"abc").decode()) is None


def test_codes_from_text_variants_and_dedupe():
    text = (
        "https://www.instagram.com/p/AAAAAAAAAAA/ x https://instagram.com/reel/BBBBBBBBBBB/?igsh=1 "
        "https://www.instagram.com/reels/CCCCCCCCCCC https://www.instagram.com/p/AAAAAAAAAAA/"
    )
    assert codes_from_text(text) == ["AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC"]


def test_url_for():
    assert url_for("AAAAAAAAAAA") == "https://www.instagram.com/p/AAAAAAAAAAA/"
