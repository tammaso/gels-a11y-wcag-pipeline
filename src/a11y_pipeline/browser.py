"""Sessione del browser (Playwright): apre le pagine come le vedrebbe un utente."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import TracebackType

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright


@dataclass
class BrowserOptions:
    viewport: tuple[int, int] = (1280, 800)
    channel: str | None = None  # es. "chrome" per usare Google Chrome installato
    headless: bool = True
    storage_state: str | None = None  # sessione salvata (login) da riusare
    settle_ms: int = 500  # attesa dopo il caricamento, per gli script della pagina
    timeout_ms: int = 30_000
    clicks: list[str] = field(default_factory=list)  # selettori da cliccare prima del controllo


def parse_viewport(value: str) -> tuple[int, int]:
    width, _, height = value.lower().partition("x")
    return int(width), int(height)


class BrowserSession:
    """Usare come context manager: ``with BrowserSession(opts) as session: ...``."""

    def __init__(self, options: BrowserOptions | None = None) -> None:
        self.options = options or BrowserOptions()
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    def __enter__(self) -> "BrowserSession":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            channel=self.options.channel, headless=self.options.headless
        )
        width, height = self.options.viewport
        self._context = self._browser.new_context(
            viewport={"width": width, "height": height},
            # Permette di iniettare il motore anche nelle pagine con Content-Security-Policy.
            bypass_csp=True,
            storage_state=self.options.storage_state,
        )
        self._context.set_default_timeout(self.options.timeout_ms)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def open(self, url: str) -> Page:
        """Apre la pagina, attende il caricamento e chiude banner/popup indicati nelle opzioni."""
        assert self._context is not None, "Usare BrowserSession come context manager"
        page = self._context.new_page()
        page.goto(url, wait_until="load")
        if self.options.settle_ms:
            page.wait_for_timeout(self.options.settle_ms)
        for selector in self.options.clicks:
            locator = page.locator(selector).first
            try:
                locator.click(timeout=2_000)
            except Exception:  # il banner può non esserci: non è un errore
                continue
            page.wait_for_timeout(200)
        return page
