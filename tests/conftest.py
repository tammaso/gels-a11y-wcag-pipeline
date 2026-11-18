from __future__ import annotations

import functools
import http.server
import os
import threading
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
PAGES = FIXTURES / "pages"


def page_uri(name: str) -> str:
    return (PAGES / name).resolve().as_uri()


@pytest.fixture(scope="session")
def axe_path() -> Path:
    from a11y_pipeline.engines.axe import find_axe_script

    try:
        return find_axe_script()
    except FileNotFoundError as exc:
        pytest.skip(str(exc))


@pytest.fixture(scope="session")
def browser_session(axe_path):
    """Un solo browser per tutta la sessione di test.

    A11Y_BROWSER_CHANNEL=chrome usa Google Chrome installato invece del Chromium di Playwright.
    """
    from a11y_pipeline.browser import BrowserOptions, BrowserSession

    options = BrowserOptions(channel=os.environ.get("A11Y_BROWSER_CHANNEL") or None, settle_ms=100)
    with BrowserSession(options) as session:
        yield session


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # niente rumore nei log dei test
        pass


def serve_directory(directory: Path) -> tuple[http.server.ThreadingHTTPServer, str]:
    handler = functools.partial(_QuietHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


@pytest.fixture
def two_origins(tmp_path):
    """Due server locali su porte diverse, cioè due origini diverse (sito proprio e sito di terzi)."""
    own_dir, other_dir = tmp_path / "own", tmp_path / "other"
    own_dir.mkdir()
    other_dir.mkdir()
    own, own_url = serve_directory(own_dir)
    other, other_url = serve_directory(other_dir)
    yield own_dir, own_url, other_dir, other_url
    own.shutdown()
    other.shutdown()
