"""Motore axe-core (Deque, MPL-2.0): https://github.com/dequelabs/axe-core

axe-core è JavaScript: lo iniettiamo nella pagina aperta da Playwright e in ogni iframe,
eseguiamo ``axe.runPartial`` frame per frame e uniamo i risultati con ``axe.finishRun``.
È lo schema usato dall'integrazione ufficiale @axe-core/playwright: funziona anche con
iframe di altre origini e con file locali, e le regole "di pagina" (titolo, lingua...)
vengono applicate solo al documento principale, come prevedono le regole ACT.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable

from a11y_pipeline.engines import is_third_party
from a11y_pipeline.models import Finding, Outcome

if TYPE_CHECKING:
    from playwright.sync_api import Frame, Page

# Le etichette di axe non sono cumulative: per arrivare a WCAG 2.2 AA servono tutte.
# https://github.com/dequelabs/axe-core/blob/develop/doc/API.md#axe-core-tags
DEFAULT_TAGS = ("wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa")

# Etichetta di un criterio: "wcag111" -> 1.1.1, "wcag1412" -> 1.4.12, "wcag2411" -> 2.4.11
_SC_TAG = re.compile(r"^wcag(\d)(\d)(\d+)$")

_HAS_AXE_JS = "() => typeof window.axe !== 'undefined'"
_FRAME_CONTEXTS_JS = "([context, options]) => axe.utils.getFrameContexts(context ?? document, options)"
_RUN_PARTIAL_JS = "([context, options]) => axe.runPartial(context ?? document, options)"
_FINISH_RUN_JS = "([partials, options]) => axe.finishRun(partials, options)"
_RULES_JS = "() => axe.getRules().map(r => ({ruleId: r.ruleId, actIds: r.actIds || []}))"


def sc_from_tag(tag: str) -> str | None:
    match = _SC_TAG.match(tag)
    return ".".join(match.groups()) if match else None


def find_axe_script() -> Path:
    """Trova axe.min.js: variabile A11Y_AXE_PATH, oppure node_modules nella cartella corrente o superiori."""
    env = os.environ.get("A11Y_AXE_PATH")
    if env:
        path = Path(env)
        if path.is_file():
            return path
        raise FileNotFoundError(f"A11Y_AXE_PATH punta a un file inesistente: {path}")
    starts = [Path.cwd(), Path(__file__).resolve()]
    for start in starts:
        for folder in (start, *start.parents):
            candidate = folder / "node_modules" / "axe-core" / "axe.min.js"
            if candidate.is_file():
                return candidate
    raise FileNotFoundError(
        "axe.min.js non trovato. Esegui `npm ci` nella cartella del progetto "
        "oppure imposta A11Y_AXE_PATH."
    )


class AxeEngine:
    name = "axe-core"

    def __init__(
        self,
        tags: Iterable[str] = DEFAULT_TAGS,
        enable_rules: Iterable[str] = (),
        disable_rules: Iterable[str] = (),
        only_rules: Iterable[str] = (),
        axe_path: str | os.PathLike | None = None,
    ) -> None:
        self.tags = tuple(tags)
        self.enable_rules = tuple(enable_rules)
        self.disable_rules = tuple(disable_rules)
        self.only_rules = tuple(only_rules)
        self.axe_path = Path(axe_path) if axe_path else find_axe_script()
        self._version: str | None = None
        self._act_ids: dict[str, tuple[str, ...]] = {}
        self._warnings: list[str] = []

    @property
    def version(self) -> str | None:
        return self._version

    def run_options(self) -> dict:
        """Opzioni passate ad axe.run()."""
        if self.only_rules:
            options: dict = {"runOnly": {"type": "rule", "values": list(self.only_rules)}}
        else:
            options = {"runOnly": {"type": "tag", "values": list(self.tags)}}
        rules = {rule: {"enabled": True} for rule in self.enable_rules}
        rules.update({rule: {"enabled": False} for rule in self.disable_rules})
        if rules:
            options["rules"] = rules
        options["resultTypes"] = ["violations", "incomplete"]
        return options

    def pop_warnings(self) -> list[str]:
        warnings, self._warnings = self._warnings, []
        return warnings

    def _inject(self, frame: "Frame") -> None:
        if not frame.evaluate(_HAS_AXE_JS):
            frame.add_script_tag(path=str(self.axe_path))

    def _run_partial(self, frame: "Frame", context: dict | None, options: dict) -> list:
        """Esegue axe nel frame e, ricorsivamente, negli iframe che contiene (in ordine)."""
        frame_contexts = frame.evaluate(_FRAME_CONTEXTS_JS, [context, options])
        partials = [frame.evaluate(_RUN_PARTIAL_JS, [context, options])]
        for item in frame_contexts:
            selector = item["frameSelector"]
            child = None
            try:
                handle = frame.locator(_css(selector)).first.element_handle(timeout=2_000)
                child = handle.content_frame() if handle else None
                if child is not None:
                    self._inject(child)
            except Exception as exc:  # es. iframe con documento non HTML (SVG, PDF)
                self._warnings.append(f"iframe non controllato ({_css(selector)}): {exc}".splitlines()[0])
                child = None
            if child is None:
                partials.append(None)
                continue
            partials.extend(self._run_partial(child, item["frameContext"], options))
        return partials

    def scan(self, page: "Page", page_url: str, state: str) -> list[Finding]:
        main = page.main_frame
        try:
            self._inject(main)
        except Exception as exc:
            first_line = str(exc).splitlines()[0]
            raise RuntimeError(
                "axe-core non è stato eseguito: il documento non è HTML oppure la pagina "
                f"si è ricaricata o ha cambiato indirizzo durante il controllo ({first_line})"
            ) from exc
        if not self._act_ids:
            self._act_ids = {r["ruleId"]: tuple(r["actIds"]) for r in main.evaluate(_RULES_JS)}
        options = self.run_options()
        partials = self._run_partial(main, None, options)
        raw = main.evaluate(_FINISH_RUN_JS, [partials, options])
        self._version = raw.get("testEngine", {}).get("version", self._version)
        frame_urls = _FrameResolver(page)
        return normalize(
            raw,
            page_url=page_url,
            state=state,
            frame_url=page.url,
            act_ids=self._act_ids,
            frame_url_for=frame_urls,
        )


def _css(selector) -> str:
    # Nello shadow DOM axe restituisce una lista; Playwright attraversa lo shadow DOM aperto.
    return selector[-1] if isinstance(selector, (list, tuple)) else selector


class _FrameResolver:
    """Ricava l'URL del frame che contiene un elemento a partire dal suo target axe."""

    def __init__(self, page: "Page") -> None:
        self.page = page
        self.cache: dict[tuple, str] = {(): page.url}

    def __call__(self, frame_path: tuple) -> str:
        if frame_path not in self.cache:
            try:
                frame = self.page.main_frame
                for selector in frame_path:
                    handle = frame.locator(_css(selector)).first.element_handle(timeout=2_000)
                    frame = handle.content_frame()
                self.cache[frame_path] = frame.url
            except Exception:
                self.cache[frame_path] = ""
        return self.cache[frame_path]


def _message(node: dict) -> str:
    if node.get("failureSummary"):
        return node["failureSummary"]
    checks = [c.get("message", "") for key in ("any", "all", "none") for c in node.get(key, [])]
    return "\n".join(m for m in checks if m)


def _selector(target: list) -> str:
    """Selettore leggibile: ">>>" separa i livelli di iframe, ">>" lo shadow DOM."""
    parts = [" >> ".join(t) if isinstance(t, list) else str(t) for t in target]
    return " >>> ".join(parts)


def normalize(
    raw: dict,
    *,
    page_url: str,
    state: str,
    frame_url: str,
    act_ids: dict[str, tuple[str, ...]] | None = None,
    frame_url_for: Callable[[tuple], str] | None = None,
) -> list[Finding]:
    """Converte il risultato di axe nel formato comune (una riga per elemento e criterio).

    ``frame_url`` è l'URL del documento principale. Per gli elementi dentro un iframe il
    target di axe contiene prima i selettori dei frame: ``frame_url_for`` li traduce nell'URL
    del frame, per distinguere i contenuti di terzi.
    """
    act_ids = act_ids or {}
    version = raw.get("testEngine", {}).get("version", "")
    findings: list[Finding] = []
    for key, outcome in (("violations", Outcome.FAILED), ("incomplete", Outcome.CANT_TELL)):
        for rule in raw.get(key, []):
            criteria = [sc for sc in map(sc_from_tag, rule.get("tags", [])) if sc]
            for node in rule.get("nodes", []):
                target = node.get("target", [])
                frame_path = tuple(tuple(t) if isinstance(t, list) else t for t in target[:-1])
                node_frame_url = frame_url
                if frame_path:
                    node_frame_url = frame_url_for(frame_path) if frame_url_for else ""
                third_party = is_third_party(node_frame_url, page_url)
                for sc in criteria:
                    findings.append(
                        Finding(
                            page_url=page_url,
                            state=state,
                            frame_url=node_frame_url,
                            third_party=third_party,
                            engine=AxeEngine.name,
                            engine_version=version,
                            rule_id=rule["id"],
                            outcome=outcome,
                            sc=sc,
                            selector=_selector(target),
                            html=node.get("html", ""),
                            message=_message(node),
                            help_url=rule.get("helpUrl", ""),
                            impact=node.get("impact") or rule.get("impact"),
                            act_rule_ids=act_ids.get(rule["id"], ()),
                        )
                    )
    return findings
