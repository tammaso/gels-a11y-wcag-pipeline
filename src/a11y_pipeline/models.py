"""Formato comune dei risultati, indipendente dal motore di controllo.

Gli esiti usano il vocabolario W3C EARL 1.0 (https://www.w3.org/TR/EARL10-Schema/):
la pipeline produce solo ``failed`` (errore rilevato) e ``cantTell`` (da verificare).
Non produce mai un esito di conformità.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class Outcome(str, Enum):
    """Esiti EARL usati dalla pipeline."""

    FAILED = "failed"
    CANT_TELL = "cantTell"


class ScStatus(str, Enum):
    """Stato di un criterio WCAG nel report riepilogativo."""

    ERRORS = "errori rilevati"
    TO_REVIEW = "da verificare"
    NO_ERRORS = "nessun errore rilevato"
    MANUAL_CHECK = "verifica manuale necessaria"
    NOT_AUTOMATABLE = "non verificabile in automatico"


@dataclass(frozen=True)
class Finding:
    """Un singolo problema rilevato su un elemento, riferito a un criterio WCAG."""

    page_url: str
    state: str
    frame_url: str
    third_party: bool
    engine: str
    engine_version: str
    rule_id: str
    outcome: Outcome
    sc: str
    selector: str
    html: str
    message: str
    help_url: str
    impact: str | None = None
    act_rule_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        data = asdict(self)
        data["outcome"] = self.outcome.value
        data["act_rule_ids"] = list(self.act_rule_ids)
        return data


@dataclass
class PageResult:
    """Risultato del controllo di una pagina (tutti gli stati e tutti i frame)."""

    url: str
    states: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
