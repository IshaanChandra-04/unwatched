"""The browser installs itself on first use, and a missing username is not an expired session."""

import subprocess
from contextlib import contextmanager

import pytest

from unwatched import browser


class _Ctx:
    pages = []

    def close(self):
        pass

    def new_page(self):
        return _Page()


class _Page:
    url = "https://www.instagram.com/"

    def goto(self, url):
        self.url = url

    def wait_for_timeout(self, ms):
        pass

    def evaluate(self, js, *args):
        return None  # no profile link on the page


def test_context_installs_chromium_when_the_browser_is_missing(tmp_path, monkeypatch):
    from playwright.sync_api import Error

    launches, installs = [], []

    class Chromium:
        def launch_persistent_context(self, *args, **kwargs):
            launches.append(kwargs)
            if len(launches) == 1:
                raise Error("Executable doesn't exist at /x/chrome\nRun playwright install")
            return _Ctx()

    class Playwright:
        chromium = Chromium()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: Playwright())
    monkeypatch.setattr(browser, "install_chromium", lambda: installs.append("installed"))
    with browser._context(tmp_path / "profile", headless=True) as ctx:
        assert isinstance(ctx, _Ctx)
    assert installs == ["installed"] and len(launches) == 2


def test_install_chromium_runs_playwright_install(monkeypatch):
    seen = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: seen.append(cmd))
    browser.install_chromium()
    assert seen[0][-4:] == ["-m", "playwright", "install", "chromium"]


def test_missing_username_is_reported_not_treated_as_an_expired_session(tmp_path, monkeypatch):
    @contextmanager
    def fake_context(profile_dir, headless):
        yield _Ctx()

    monkeypatch.setattr(browser, "_context", fake_context)
    with pytest.raises(RuntimeError, match="username"):
        browser.sweep_saved(set(), profile_dir=tmp_path, headless=True, wait_ms=0)
