"""Live collection through Playwright on a browser profile the user signs into once."""

import logging
import re
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from unwatched.fetch import COOKIES_PATH
from unwatched.posts import now_iso
from unwatched.shortcode import codes_from_text, shortcode_from_cache_key

PROFILE_DIR = Path.home() / ".unwatched" / "browser-profile"
log = logging.getLogger("unwatched")

# Finds the largest scrollable element (the DM list) and reports whether it sits at its
# start; in a column-reverse list the start is the most negative scrollTop.
_SCROLLER_JS = """
() => {
  const els = [...document.querySelectorAll('*')].filter(e =>
    e.scrollHeight > e.clientHeight + 10 && /(auto|scroll)/.test(getComputedStyle(e).overflowY));
  els.sort((a, b) => b.scrollHeight - a.scrollHeight);
  return els[0] || document.scrollingElement;
}
"""
_COLLECT_JS = f"""
() => {{
  const sc = ({_SCROLLER_JS})();
  const reverse = getComputedStyle(sc).flexDirection === 'column-reverse';
  const maxUp = sc.scrollHeight - sc.clientHeight;
  const top = reverse ? sc.scrollTop <= -maxUp + 2 : sc.scrollTop <= 2;
  const srcs = [...document.querySelectorAll('img[src*="ig_cache_key"]')].map(i => i.src);
  const links = document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]');
  return {{srcs, hrefs: [...links].map(a => a.href), top}};
}}
"""
_SCROLL_UP_JS = f"(step) => {{ ({_SCROLLER_JS})().scrollTop -= step; }}"
_GRID_JS = """
() => ({
  hrefs: [...document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]')].map(a => a.href),
  top: false,
})
"""
_PROFILE_LINK_JS = """
() => {
  const a = [...document.querySelectorAll('a[href]')]
    .find(a => a.querySelector('img[alt$="profile picture"]'));
  return a ? a.getAttribute('href') : null;
}
"""


class LoginRequired(Exception):
    pass


def codes_from_srcs(srcs: list[str]) -> list[str]:
    codes = []
    for src in srcs:
        for key in parse_qs(urlparse(src).query).get("ig_cache_key", []):
            code = shortcode_from_cache_key(key)
            if code:
                codes.append(code)
    return list(dict.fromkeys(codes))


@contextmanager
def _context(profile_dir: Path, headless: bool):
    from playwright.sync_api import sync_playwright

    profile_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(profile_dir), headless=headless, viewport={"width": 1280, "height": 900}
        )
        try:
            yield ctx
        finally:
            ctx.close()


def _has_session(ctx) -> bool:
    return any(c["name"] == "sessionid" and "instagram.com" in c["domain"] for c in ctx.cookies())


def login(profile_dir: Path = PROFILE_DIR, timeout_s: int = 600) -> bool:
    """Open Instagram in the tool's window and wait for the user to sign in. Types nothing."""
    with _context(profile_dir, headless=False) as ctx:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.instagram.com/")
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if _has_session(ctx):
                return True
            time.sleep(2)
        return False


def export_cookies(profile_dir: Path = PROFILE_DIR, out: Path = COOKIES_PATH) -> Path:
    """Write the profile's instagram.com cookies in Netscape format for yt-dlp."""
    lines = ["# Netscape HTTP Cookie File"]
    with _context(profile_dir, headless=True) as ctx:
        if not _has_session(ctx):
            raise LoginRequired
        for c in ctx.cookies():
            if "instagram.com" not in c["domain"]:
                continue
            expires = int(c["expires"]) if c.get("expires", -1) > 0 else 0
            lines.append(
                "\t".join(
                    [
                        c["domain"],
                        "TRUE" if c["domain"].startswith(".") else "FALSE",
                        c["path"],
                        "TRUE" if c["secure"] else "FALSE",
                        str(expires),
                        c["name"],
                        c["value"],
                    ]
                )
            )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        out.chmod(0o600)
    except OSError:
        pass
    return out


def _check_login(page) -> None:
    if "/accounts/login" in page.url:
        raise LoginRequired


def _sweep(
    page, collect_js: str, scroll, known: set[str], full: bool, stop_after_known: int, wait_ms: int
) -> list[str]:
    """Scroll toward older items collecting codes until the streak or the start says stop."""
    collected: list[str] = []
    seen: set[str] = set()
    streak = 0
    idle_at_top = 0
    while True:
        state = page.evaluate(collect_js)
        codes = codes_from_srcs(state["srcs"]) if "srcs" in state else []
        codes += codes_from_text(" ".join(state["hrefs"]))
        new_this_round = 0
        for code in codes:
            if code in seen or code in known:
                streak += 1
            else:
                streak = 0
                seen.add(code)
                collected.append(code)
                new_this_round += 1
            if not full and streak >= stop_after_known:
                return collected
        if state["top"] and new_this_round == 0:
            idle_at_top += 1
            if idle_at_top >= 3:
                return collected
        else:
            idle_at_top = 0
        scroll()
        page.wait_for_timeout(wait_ms)


def _found(codes: list[str], kind: str, name: str) -> list[tuple[str, dict, None]]:
    ts = now_iso()
    return [(c, {"kind": kind, "name": name, "via": "live", "ts": ts}, None) for c in codes]


def sweep_dm(
    url: str,
    known: set[str],
    profile_dir: Path = PROFILE_DIR,
    full: bool = False,
    stop_after_known: int = 20,
    headless: bool = False,
    wait_ms: int = 700,
) -> list[tuple[str, dict, None]]:
    with _context(profile_dir, headless) as ctx:
        page = ctx.new_page()
        page.goto(url)
        _check_login(page)
        page.wait_for_timeout(wait_ms)
        title = page.title().split(" • ")[0].strip()
        name = title or re.sub(r"\W+", "", urlparse(url).path.rsplit("/", 2)[-2])
        codes = _sweep(
            page,
            _COLLECT_JS,
            lambda: page.evaluate(_SCROLL_UP_JS, 450),
            known,
            full,
            stop_after_known,
            wait_ms,
        )
    log.info("dm sweep of %s found %d new", name, len(codes))
    return _found(codes, "dm", name)


def _grid(page, url: str, known: set[str], full: bool, wait_ms: int) -> list[str]:
    page.goto(url)
    _check_login(page)
    page.wait_for_timeout(wait_ms)
    collected: list[str] = []
    rounds_without_new = 0
    while rounds_without_new < 3:
        codes = _sweep_once_grid(page, known, collected)
        if codes:
            collected += codes
            rounds_without_new = 0
            if not full and len(codes) < 12:  # a partial screen of new tiles: reached known ground
                break
        else:
            rounds_without_new += 1
        page.evaluate("() => window.scrollBy(0, 900)")
        page.wait_for_timeout(wait_ms)
    return collected


def _sweep_once_grid(page, known: set[str], collected: list[str]) -> list[str]:
    hrefs = page.evaluate(_GRID_JS)["hrefs"]
    return [c for c in codes_from_text(" ".join(hrefs)) if c not in known and c not in collected]


def sweep_saved(
    known: set[str],
    profile_dir: Path = PROFILE_DIR,
    full: bool = False,
    username: str | None = None,
    headless: bool = False,
    wait_ms: int = 700,
) -> list[tuple[str, dict, None]]:
    out: list[tuple[str, dict, None]] = []
    with _context(profile_dir, headless) as ctx:
        page = ctx.new_page()
        if not username:
            page.goto("https://www.instagram.com/")
            _check_login(page)
            page.wait_for_timeout(wait_ms)
            href = page.evaluate(_PROFILE_LINK_JS)
            if not href:
                raise LoginRequired
            username = href.strip("/").split("/")[0]
        base = f"https://www.instagram.com/{username}/saved/"
        out += _found(_grid(page, base + "all-posts/", known, full, wait_ms), "saved", "saved")
        page.goto(base)
        _check_login(page)
        page.wait_for_timeout(wait_ms)
        collections = page.evaluate(
            """() => [...document.querySelectorAll('a[href*="/saved/"]')]
                 .filter(a => !a.href.includes('all-posts') && a.innerText.trim())
                 .map(a => [a.href, a.innerText.trim().split('\\n')[0]])"""
        )
        for href, name in collections:
            codes = _grid(page, href, known | {c for c, _, _ in out}, full, wait_ms)
            out += _found(codes, "saved", name)
    log.info("saved sweep found %d new", len(out))
    return out
