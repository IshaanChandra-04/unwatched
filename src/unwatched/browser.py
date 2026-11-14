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

# The DM list is the largest scrollable element; in its column-reverse layout the oldest
# message sits at the most negative scrollTop, which is where the sweep ends.
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
  const end = reverse ? sc.scrollTop <= -maxUp + 2 : sc.scrollTop <= 2;
  const srcs = [...document.querySelectorAll('img[src*="ig_cache_key"]')].map(i => i.src);
  const links = document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]');
  return {{srcs, hrefs: [...links].map(a => a.href), end}};
}}
"""
_SCROLL_UP_JS = f"(step) => {{ ({_SCROLLER_JS})().scrollTop -= step; }}"
# A saved grid is the page itself, newest first; the sweep ends at the bottom of the page.
_GRID_JS = """
() => {
  const links = document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]');
  const end = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2;
  return {hrefs: [...links].map(a => a.href), end};
}
"""
_SCROLL_DOWN_JS = "(step) => window.scrollBy(0, step)"
# The conversation header is the first heading in the nearest ancestor of the message list
# that has one; the inbox sidebar's headings live in a sibling column and are never reached.
_THREAD_HEADER_JS = f"""
() => {{
  let el = ({_SCROLLER_JS})();
  while (el && el !== document.body) {{
    const h = el.querySelector('h1, h2');
    if (h) return h.textContent;
    el = el.parentElement;
  }}
  return null;
}}
"""
_PROFILE_LINK_JS = """
() => {
  const a = [...document.querySelectorAll('a[href]')]
    .find(a => a.querySelector('img[alt$="profile picture"]'));
  return a ? a.getAttribute('href') : null;
}
"""
_COLLECTIONS_JS = """
() => [...document.querySelectorAll('a[href*="/saved/"]')]
  .filter(a => !a.href.includes('all-posts') && a.innerText.trim())
  .map(a => [a.href, a.innerText.trim().split('\\n')[0]])
"""

Found = tuple[str, dict, None]


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
    for d in (profile_dir.parent, profile_dir):
        try:
            d.chmod(0o700)  # no-op on Windows, where the home folder's ACL already applies
        except OSError:
            pass
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


def _wait_for_content(page, collect_js: str, timeout_ms: int = 15000) -> None:
    """Instagram fills the page after its load event; wait until something is there."""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        state = page.evaluate(collect_js)
        if state.get("srcs") or state.get("hrefs"):
            return
        page.wait_for_timeout(250)


def _sweep(
    page,
    collect_js: str,
    scroll_js: str,
    known: set[str],
    full: bool,
    stop_after_known: int,
    wait_ms: int,
) -> list[str]:
    """Scroll toward older items collecting codes until the streak or the end says stop."""
    _wait_for_content(page, collect_js)
    collected: list[str] = []
    seen: set[str] = set()
    streak = 0
    idle_at_end = 0
    rounds = 0
    while True:
        rounds += 1
        if rounds % 20 == 0:
            log.info("sweep: %d rounds, %d new so far", rounds, len(collected))
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
        if state["end"] and new_this_round == 0:
            idle_at_end += 1
            if idle_at_end >= 3:
                return collected
        else:
            idle_at_end = 0
        page.evaluate(scroll_js, 450 if "srcs" in state else 900)
        page.wait_for_timeout(wait_ms)


def _found(codes: list[str], kind: str, name: str) -> list[Found]:
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
) -> list[Found]:
    with _context(profile_dir, headless) as ctx:
        page = ctx.new_page()
        page.goto(url)
        _check_login(page)
        page.wait_for_timeout(wait_ms)
        # the tab title is "Instagram • Messages"; the thread's name is the conversation header
        header = page.evaluate(_THREAD_HEADER_JS) or ""
        name = header.strip() or re.sub(r"\W+", "", urlparse(url).path.rsplit("/", 2)[-2])
        codes = _sweep(page, _COLLECT_JS, _SCROLL_UP_JS, known, full, stop_after_known, wait_ms)
    log.info("dm sweep of %s found %d new", name, len(codes))
    return _found(codes, "dm", name)


def _grid(page, url: str, known: set[str], full: bool, stop_after_known: int, wait_ms: int):
    page.goto(url)
    _check_login(page)
    page.wait_for_timeout(wait_ms)
    return _sweep(page, _GRID_JS, _SCROLL_DOWN_JS, known, full, stop_after_known, wait_ms)


def sweep_grid(
    url: str,
    known: set[str],
    name: str,
    profile_dir: Path = PROFILE_DIR,
    full: bool = False,
    stop_after_known: int = 20,
    headless: bool = False,
    wait_ms: int = 700,
) -> list[Found]:
    """Sweep one grid page (a saved collection) newest first."""
    with _context(profile_dir, headless) as ctx:
        codes = _grid(ctx.new_page(), url, known, full, stop_after_known, wait_ms)
    return _found(codes, "saved", name)


def sweep_saved(
    known: set[str],
    profile_dir: Path = PROFILE_DIR,
    full: bool = False,
    username: str | None = None,
    headless: bool = False,
    wait_ms: int = 700,
) -> list[Found]:
    out: list[Found] = []
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
        out += _found(_grid(page, base + "all-posts/", known, full, 20, wait_ms), "saved", "saved")
        page.goto(base)
        _check_login(page)
        page.wait_for_timeout(wait_ms)
        for href, name in page.evaluate(_COLLECTIONS_JS):
            already = known | {c for c, _, _ in out}
            out += _found(_grid(page, href, already, full, 20, wait_ms), "saved", name)
    log.info("saved sweep found %d new", len(out))
    return out
