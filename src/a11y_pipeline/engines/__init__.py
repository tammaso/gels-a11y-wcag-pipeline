"""Motori di controllo.

Ogni motore implementa la stessa interfaccia (``Engine``), così aggiungerne uno nuovo
(per esempio IBM Equal Access) non richiede modifiche al resto della pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol
from urllib.parse import urlparse

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from a11y_pipeline.models import Finding


class Engine(Protocol):
    name: str

    @property
    def version(self) -> str | None: ...

    def scan(self, page: "Page", page_url: str, state: str) -> list["Finding"]:
        """Controlla la pagina nello stato attuale, in tutti i suoi frame."""
        ...


def origin(url: str) -> str | None:
    """Origine (schema + host) di un URL; None per about:blank/about:srcdoc."""
    parsed = urlparse(url)
    if parsed.scheme in ("about", "data", "blob", ""):
        return None
    if parsed.scheme == "file":
        return "file://"
    return f"{parsed.scheme}://{parsed.netloc}"


def is_third_party(frame_url: str, page_url: str) -> bool:
    """True se il frame ha un'origine diversa da quella della pagina (contenuto di terzi)."""
    frame_origin = origin(frame_url)
    return frame_origin is not None and frame_origin != origin(page_url)


def get_engine(name: str, **options) -> Engine:
    if name == "axe":
        from a11y_pipeline.engines.axe import AxeEngine

        return AxeEngine(**options)
    raise ValueError(f"Motore sconosciuto: {name!r}. Disponibili: axe")
