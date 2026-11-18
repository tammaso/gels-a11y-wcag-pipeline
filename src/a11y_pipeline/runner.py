"""Esecuzione dei controlli: pagine × stati × motori."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Callable

from playwright.sync_api import Page

from a11y_pipeline.browser import BrowserSession
from a11y_pipeline.engines import Engine
from a11y_pipeline.models import PageResult

# Uno scenario riceve la pagina e una funzione check(etichetta) da chiamare
# ogni volta che la pagina si trova in uno stato da controllare.
Scenario = Callable[[Page, Callable[[str], None]], None]

INITIAL_STATE = "iniziale"


def default_scenario(page: Page, check: Callable[[str], None]) -> None:
    check(INITIAL_STATE)


def load_scenario(path: str | Path) -> Scenario:
    """Carica da un file Python la funzione ``run(page, check)``."""
    path = Path(path)
    spec = importlib.util.spec_from_file_location(f"a11y_scenario_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Impossibile caricare lo scenario: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "run"):
        raise AttributeError(f"Lo scenario {path} deve definire una funzione run(page, check)")
    return module.run


def check_page(
    session: BrowserSession,
    url: str,
    engines: list[Engine],
    scenario: Scenario = default_scenario,
) -> PageResult:
    result = PageResult(url=url)
    page = None
    try:
        page = session.open(url)

        def check(state: str) -> None:
            result.states.append(state)
            for engine in engines:
                result.findings.extend(engine.scan(page, url, state))
                pop = getattr(engine, "pop_warnings", None)
                if pop:
                    result.warnings.extend(f"[{state}] {w}" for w in pop())

        scenario(page, check)
    except Exception as exc:  # una pagina che non si apre non deve fermare le altre
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        if page is not None:
            page.close()
    return result


def check_pages(
    session: BrowserSession,
    urls: list[str],
    engines: list[Engine],
    scenario: Scenario = default_scenario,
    progress: Callable[[int, int, str], None] | None = None,
) -> list[PageResult]:
    results = []
    for index, url in enumerate(urls, start=1):
        if progress:
            progress(index, len(urls), url)
        results.append(check_page(session, url, engines, scenario))
    return results
