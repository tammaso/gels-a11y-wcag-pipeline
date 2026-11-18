"""Catalogo dei 55 criteri WCAG 2.2 A/AA con fascia di verificabilità e clausole EN 301 549."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

import yaml

LEGAL_REFERENCE = "EN 301 549 v3.2.1"
FUTURE_REFERENCE = "EN 301 549 v4.1.1"


@dataclass(frozen=True)
class Criterion:
    id: str
    title: str
    level: str
    since: str
    tier: int

    @property
    def en301549_v3(self) -> str | None:
        """Clausola della EN 301 549 v3.2.1 (basata su WCAG 2.1): None per i criteri nuovi della 2.2."""
        return f"9.{self.id}" if self.since in ("2.0", "2.1") else None

    @property
    def en301549_v4(self) -> str:
        """Clausola della EN 301 549 v4.1.1 (basata su WCAG 2.2)."""
        return f"9.{self.id}"

    @property
    def legally_required_now(self) -> bool:
        """True se il criterio è richiesto dal riferimento di legge attuale (EN 301 549 v3.2.1)."""
        return self.en301549_v3 is not None

    @property
    def url(self) -> str:
        return f"https://www.w3.org/WAI/WCAG22/Understanding/{_slug(self.title)}.html"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "level": self.level,
            "since": self.since,
            "tier": self.tier,
            "en301549_v3": self.en301549_v3,
            "en301549_v4": self.en301549_v4,
            "legally_required_now": self.legally_required_now,
        }


def _slug(title: str) -> str:
    keep = "".join(c.lower() if c.isalnum() else " " for c in title)
    return "-".join(keep.split())


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Criterion]:
    """Restituisce i criteri indicizzati per numero, nell'ordine del catalogo."""
    text = resources.files("a11y_pipeline").joinpath("data/catalog.yaml").read_text("utf-8")
    raw = yaml.safe_load(text)["criteria"]
    return {
        item["id"]: Criterion(
            id=item["id"],
            title=item["title"],
            level=item["level"],
            since=str(item["since"]),
            tier=int(item["tier"]),
        )
        for item in raw
    }


def sort_key(sc: str) -> tuple[int, ...]:
    """Ordina i numeri dei criteri in modo naturale (1.4.3 prima di 1.4.10)."""
    return tuple(int(part) for part in sc.split("."))
