"""Live collection through Playwright on a browser profile the user signs into once."""

import logging
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from unwatched.fetch import COOKIES_PATH, number_pictures, read_meta, update_meta
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
# The conversation header is the last heading that precedes the message list in document order;
# the inbox sidebar's headings come earlier.
_THREAD_HEADER_JS = f"""
() => {{
  const sc = ({_SCROLLER_JS})();
  const before = [...document.querySelectorAll('h1, h2')]
    .filter(h => h.compareDocumentPosition(sc) & Node.DOCUMENT_POSITION_FOLLOWING);
  return before.length ? before[before.length - 1].textContent : null;
}}
"""
_PROFILE_LINK_JS = """
() => {
  const a = [...document.querySelectorAll('a[href]')]
    .find(a => a.querySelector('img[alt$="profile picture"]'));
  return a ? a.getAttribute('href') : null;
}
"""
# A collection link is /<user>/saved/<name>/<numeric id>/; the saved page's own tabs
# (all-posts, audio, ...) have no id and are not grids of posts.
_COLLECTIONS_JS = """
() => [...document.querySelectorAll('a[href*="/saved/"]')]
  .filter(a => /\\/saved\\/[^/]+\\/\\d+\\/?$/.test(a.href) && a.innerText.trim())
  .map(a => [a.href, a.innerText.trim().split('\\n')[0]])
"""
# A post page: the slides are the large images in the article (the avatar is small), srcset
# names the sizes, and the carousel advances with its Next button. The caption is the heading.
_POST_JS = """
() => {
  const abs = (u) => new URL(u, location.href).href;
  const pick = (img) => {
    if (!img.srcset) return abs(img.currentSrc || img.src);
    const cands = img.srcset.split(',').map(s => s.trim().split(/\\s+/))
      .map(([u, w]) => [u, parseInt(w) || 0]).sort((a, b) => b[1] - a[1]);
    return abs(cands[0][0]);
  };
  const imgs = [...document.querySelectorAll('article img')]
    .filter(i => i.getBoundingClientRect().width > 200);
  const h1 = document.querySelector('article h1') || document.querySelector('h1');
  return {srcs: imgs.map(pick), next: !!document.querySelector('button[aria-label="Next"]'),
          caption: h1 ? h1.innerText : null};
}
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


def install_chromium() -> None:
    """Download the browser Playwright drives (about 200 MB), once."""
    log.info("downloading the browser (about 200 MB, first time only)")
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)


@contextmanager
def _context(profile_dir: Path, headless: bool):
    from playwright.sync_api import Error, sync_playwright

    profile_dir.mkdir(parents=True, exist_ok=True)
    for d in (profile_dir.parent, profile_dir):
        try:
            d.chmod(0o700)  # no-op on Windows, where the home folder's ACL already applies
        except OSError:
            pass
    with sync_playwright() as p:

        def launch():
            return p.chromium.launch_persistent_context(
                str(profile_dir), headless=headless, viewport={"width": 1280, "height": 900}
            )

        try:
            ctx = launch()
        except Error as e:
            if "Executable doesn't exist" not in str(e):
                raise
            install_chromium()
            ctx = launch()
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
            if _has_session(ctx) and not _is_blocked(page.url):
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


def _is_blocked(url: str) -> bool:
    """A sign-in page or an Instagram checkpoint: nothing can be read until the user acts."""
    return "/accounts/login" in url or "/challenge" in url


def _check_login(page) -> None:
    if _is_blocked(page.url):
        raise LoginRequired


def _wait_for_content(page, collect_js: str, timeout_ms: int = 15000) -> None:
    """Instagram fills the page after its load event; wait until something is there."""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        state = page.evaluate(collect_js)
        if state.get("srcs") or state.get("hrefs"):
            return
        page.wait_for_timeout(250)
    log.warning("no posts appeared on %s within %d s; layout change?", page.url, timeout_ms // 1000)


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
            if code in seen:
                continue  # still on screen from an earlier round; says nothing about the past
            if code in known:
                streak += 1
            else:
                streak = 0
                collected.append(code)
                new_this_round += 1
            seen.add(code)
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
        _wait_for_content(page, _COLLECT_JS)
        # the tab title is "Instagram • Messages"; the thread's name is the conversation header
        header = page.evaluate(_THREAD_HEADER_JS) or ""
        segment = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
        name = header.strip() or re.sub(r"\W+", "", segment)
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
            if not href:  # the lookup reads English alt text; another language lands here
                raise RuntimeError(
                    "could not find your username on the home page; "
                    'set username = "<your handle>" in unwatched.toml'
                )
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


def _slides(page, wait_ms: int) -> tuple[list[str], str | None]:
    """Walk a post's carousel with its Next button, collecting the largest URL of every slide."""
    urls: list[str] = []
    caption = None
    for _ in range(20):  # shortcut: Instagram allows 20 slides and the button is English-only
        state = page.evaluate(_POST_JS)
        caption = caption or state["caption"]
        urls += [u for u in state["srcs"] if u not in urls]
        if not state["next"]:
            break
        page.click('button[aria-label="Next"]')
        page.wait_for_timeout(wait_ms)
    return urls, caption


def fetch_pictures(
    work: Path,
    codes: list[str],
    profile_dir: Path = PROFILE_DIR,
    headless: bool = False,
    wait_ms: int = 700,
    base_url: str = "https://www.instagram.com/p/",
) -> dict[str, int]:
    """Download every slide and the caption of image posts through the signed-in browser."""
    counts = {"fetched": 0, "failed": 0}
    with _context(profile_dir, headless) as ctx:
        page = ctx.new_page()
        for code in codes:
            try:
                page.goto(f"{base_url}{code}/")
                _check_login(page)
                _wait_for_content(page, _POST_JS, timeout_ms=max(1000, wait_ms * 20))
                urls, caption = _slides(page, wait_ms)
                if not urls:
                    raise RuntimeError("no pictures on the page")
                folder = work / "frames" / code
                shutil.rmtree(folder, ignore_errors=True)  # the cover yt-dlp fetched
                folder.mkdir(parents=True)
                for i, url in enumerate(urls, 1):
                    resp = ctx.request.get(url)
                    if not resp.ok:
                        raise RuntimeError(f"picture {i}: HTTP {resp.status}")
                    suffix = ".webp" if "webp" in resp.headers.get("content-type", "") else ".jpg"
                    (folder / f"{i}{suffix}").write_bytes(resp.body())
                number_pictures(folder)
                fields = {"slides": len(urls), "pictures_error": None}
                if caption:
                    fields["caption"] = caption
                update_meta(work, code, **fields)
                counts["fetched"] += 1
                log.info("pictures %s: %d slides", code, len(urls))
            except LoginRequired:
                raise
            except Exception as e:  # one post must not stop the rest
                tries = read_meta(work, code).get("pictures_retries", 0) + 1
                update_meta(work, code, pictures_error=str(e)[-500:], pictures_retries=tries)
                counts["failed"] += 1
                log.warning("pictures %s failed: %s", code, e)
    return counts
