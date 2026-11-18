"""Da dove arrivano le pagine da controllare.

Ogni elemento può essere:
  - un URL http(s) di una pagina pubblicata;
  - un URL o un file di sitemap (.xml): si controllano tutte le pagine elencate;
  - un file HTML locale (prima della pubblicazione);
  - una cartella: tutti i file .html/.htm al suo interno;
  - un file .txt o .csv con un elemento per riga (prima colonna).
"""

from __future__ import annotations

import csv
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

_SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
_HTML_SUFFIXES = {".html", ".htm", ".xhtml"}


def _is_url(item: str) -> bool:
    return item.startswith(("http://", "https://", "file://"))


def _sitemap_urls(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    urls = [el.text.strip() for el in root.iter(f"{_SITEMAP_NS}loc") if el.text]
    # Un indice di sitemap rimanda ad altre sitemap: le espandiamo.
    if root.tag == f"{_SITEMAP_NS}sitemapindex":
        expanded: list[str] = []
        for url in urls:
            expanded.extend(resolve_targets([url]))
        return expanded
    return urls


def _read_list(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        if path.suffix.lower() == ".csv":
            rows = [row[0].strip() for row in csv.reader(handle) if row and row[0].strip()]
        else:
            rows = [line.strip() for line in handle if line.strip()]
    return [row for row in rows if not row.startswith("#")]


def resolve_targets(items: list[str]) -> list[str]:
    """Trasforma l'elenco di input in un elenco di URL da aprire nel browser, senza duplicati."""
    targets: list[str] = []
    for item in items:
        if _is_url(item):
            if item.lower().endswith(".xml"):
                with urllib.request.urlopen(item, timeout=30) as response:
                    targets.extend(_sitemap_urls(response.read().decode("utf-8")))
            else:
                targets.append(item)
            continue
        path = Path(item).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Non trovato: {item}")
        if path.is_dir():
            targets.extend(
                p.resolve().as_uri()
                for p in sorted(path.rglob("*"))
                if p.is_file() and p.suffix.lower() in _HTML_SUFFIXES
            )
        elif path.suffix.lower() in _HTML_SUFFIXES:
            targets.append(path.resolve().as_uri())
        elif path.suffix.lower() == ".xml":
            targets.extend(_sitemap_urls(path.read_text("utf-8")))
        elif path.suffix.lower() in (".txt", ".csv"):
            targets.extend(resolve_targets(_read_list(path)))
        else:
            raise ValueError(f"Tipo di input non riconosciuto: {item}")
    return list(dict.fromkeys(targets))
