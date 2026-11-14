"""Instagram shortcodes: media ids, thumbnail cache keys and URLs."""

import base64
import binascii
import re
from urllib.parse import unquote

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
_URL = re.compile(r"instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)")


def media_id_to_shortcode(media_id: int) -> str:
    chars = []
    while media_id > 0:
        media_id, rem = divmod(media_id, 64)
        chars.append(ALPHABET[rem])
    return "".join(reversed(chars)) or "A"


def shortcode_from_cache_key(key: str) -> str | None:
    """Decode a thumbnail's ``ig_cache_key``: base64 of ``<media id>[_<n>]``, URL-encoded, and
    followed on the CDN by a suffix such as ``.3-ccb7-5``."""
    try:
        raw = base64.b64decode(unquote(key).split(".", 1)[0], validate=True).decode("ascii")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
    digits = raw.split("_", 1)[0]
    return media_id_to_shortcode(int(digits)) if digits.isdigit() else None


def codes_from_text(text: str) -> list[str]:
    return list(dict.fromkeys(_URL.findall(text)))


def url_for(code: str) -> str:
    return f"https://www.instagram.com/p/{code}/"
