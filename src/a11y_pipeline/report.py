"""Riepilogo per criterio e report in JSON (per le macchine) e HTML (per le persone)."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from a11y_pipeline import __version__
from a11y_pipeline.catalog import FUTURE_REFERENCE, LEGAL_REFERENCE, Criterion, load_catalog, sort_key
from a11y_pipeline.models import Finding, Outcome, PageResult, ScStatus

DISCLAIMER = (
    "Il controllo automatico rileva solo una parte delle non conformità. "
    "L'assenza di errori non significa che la pagina sia conforme: "
    "i criteri segnati come da verificare o non verificabili in automatico richiedono una verifica manuale."
)


def unique(findings: list[Finding]) -> list[Finding]:
    """Toglie i doppioni dello stesso problema rilevato in più stati della stessa pagina."""
    seen: dict[tuple, Finding] = {}
    for f in findings:
        key = (f.page_url, f.frame_url, f.engine, f.rule_id, f.selector, f.sc, f.outcome)
        seen.setdefault(key, f)
    return list(seen.values())


@dataclass
class CriterionSummary:
    criterion: Criterion
    status: ScStatus
    failed: int
    cant_tell: int
    third_party: int

    def to_dict(self) -> dict:
        return {
            **self.criterion.to_dict(),
            "status": self.status.value,
            "failed": self.failed,
            "cant_tell": self.cant_tell,
            "third_party": self.third_party,
        }


def summarize(findings: list[Finding]) -> list[CriterionSummary]:
    """Stato di ciascuno dei 55 criteri. I contenuti di terzi sono contati a parte."""
    own = [f for f in unique(findings) if not f.third_party]
    failed = Counter(f.sc for f in own if f.outcome is Outcome.FAILED)
    cant_tell = Counter(f.sc for f in own if f.outcome is Outcome.CANT_TELL)
    third = Counter(f.sc for f in unique(findings) if f.third_party)
    summaries = []
    for sc, criterion in load_catalog().items():
        if failed[sc]:
            status = ScStatus.ERRORS
        elif cant_tell[sc]:
            status = ScStatus.TO_REVIEW
        elif criterion.tier == 1:
            status = ScStatus.NO_ERRORS
        elif criterion.tier == 2:
            status = ScStatus.MANUAL_CHECK
        else:
            status = ScStatus.NOT_AUTOMATABLE
        summaries.append(CriterionSummary(criterion, status, failed[sc], cant_tell[sc], third[sc]))
    return summaries


def blocking_findings(findings: list[Finding], fail_on: str) -> list[Finding]:
    """Errori che fanno fallire la pipeline.

    fail_on:
      "errori"              ogni errore su un criterio del catalogo (contenuti propri)
      "errori-obbligatori"  solo i criteri richiesti oggi dalla EN 301 549 v3.2.1
      "nessuno"             la pipeline non fallisce mai (solo report)
    """
    if fail_on == "nessuno":
        return []
    catalog = load_catalog()
    blocking = []
    for f in unique(findings):
        criterion = catalog.get(f.sc)
        if f.third_party or f.outcome is not Outcome.FAILED or criterion is None:
            continue
        if fail_on == "errori-obbligatori" and not criterion.legally_required_now:
            continue
        blocking.append(f)
    return blocking


def build_report(results: list[PageResult], engines: list[dict]) -> dict:
    catalog = load_catalog()
    findings = [f for r in results for f in r.findings]
    deduped = unique(findings)

    def enrich(f: Finding) -> dict:
        data = f.to_dict()
        criterion = catalog.get(f.sc)
        data["in_catalog"] = criterion is not None
        if criterion:
            data.update(
                level=criterion.level,
                tier=criterion.tier,
                en301549_v3=criterion.en301549_v3,
                en301549_v4=criterion.en301549_v4,
                legally_required_now=criterion.legally_required_now,
            )
        return data

    return {
        "tool": {"name": "gels-a11y-wcag-pipeline", "version": __version__},
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "technical_reference": "WCAG 2.2, livelli A e AA",
        "legal_reference": LEGAL_REFERENCE,
        "future_reference": FUTURE_REFERENCE,
        "disclaimer": DISCLAIMER,
        "engines": engines,
        "pages": [
            {
                "url": r.url,
                "states": r.states,
                "error": r.error,
                "warnings": r.warnings,
                "failed": sum(1 for f in unique(r.findings) if f.outcome is Outcome.FAILED and not f.third_party),
                "cant_tell": sum(1 for f in unique(r.findings) if f.outcome is Outcome.CANT_TELL and not f.third_party),
            }
            for r in results
        ],
        "criteria": [s.to_dict() for s in summarize(findings)],
        "findings": [enrich(f) for f in sorted(deduped, key=lambda f: (f.page_url, sort_key(f.sc), f.rule_id))],
    }


def write_json(report: dict, path: Path) -> None:
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

_CSS = """
body{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;margin:0 auto;max-width:72rem;
padding:1.5rem;line-height:1.5;color:#1a1a1a;background:#fff}
h1{font-size:1.6rem}h2{font-size:1.3rem;margin-top:2.5rem}h3{font-size:1.1rem}
table{border-collapse:collapse;width:100%;margin:1rem 0}
th,td{border:1px solid #c4c4c4;padding:.4rem .6rem;text-align:left;vertical-align:top}
th{background:#f0f0f0}
.st{font-weight:600;white-space:nowrap}
.st-errori{color:#a40000}.st-da{color:#7a4a00}.st-nessun{color:#1d5e20}.st-verifica,.st-non{color:#444}
.note{background:#fff7e0;border-left:4px solid #b07700;padding:.75rem 1rem}
code{font-size:.85em;word-break:break-all;background:#f4f4f4;padding:.1rem .25rem}
.cards{display:flex;gap:1rem;flex-wrap:wrap;padding:0;list-style:none}
.cards li{border:1px solid #c4c4c4;border-radius:.4rem;padding:.6rem 1rem;min-width:9rem}
.cards strong{display:block;font-size:1.5rem}
details{margin:.5rem 0}summary{cursor:pointer}
"""


def _status_class(status: str) -> str:
    return "st st-" + status.split()[0]


def _tier_label(tier: int) -> str:
    return {1: "1 – automatico", 2: "2 – da verificare", 3: "3 – manuale"}[tier]


def render_html(report: dict) -> str:
    criteria = report["criteria"]
    findings = report["findings"]
    status_counts = Counter(c["status"] for c in criteria)
    own_failed = sum(1 for f in findings if f["outcome"] == "failed" and not f["third_party"])
    own_review = sum(1 for f in findings if f["outcome"] == "cantTell" and not f["third_party"])
    engines = ", ".join(f'{e["name"]} {e.get("version") or ""}'.strip() for e in report["engines"])

    out = [
        '<!DOCTYPE html><html lang="it"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Report di accessibilità – WCAG 2.2 A/AA</title>",
        f"<style>{_CSS}</style></head><body><main>",
        "<h1>Report di accessibilità – WCAG 2.2 A/AA</h1>",
        f'<p>Generato il {escape(report["generated_at"])} con {escape(engines)}. '
        f'Riferimento di legge: {escape(report["legal_reference"])}.</p>',
        f'<p class="note">{escape(report["disclaimer"])}</p>',
        '<h2 id="sintesi">Sintesi</h2><ul class="cards">',
        f'<li><strong>{len(report["pages"])}</strong> pagine controllate</li>',
        f"<li><strong>{own_failed}</strong> errori rilevati</li>",
        f"<li><strong>{own_review}</strong> elementi da verificare</li>",
        f'<li><strong>{status_counts.get(ScStatus.ERRORS.value, 0)}</strong> criteri con errori</li>',
        "</ul>",
    ]

    failed_pages = [p for p in report["pages"] if p["error"]]
    if failed_pages:
        out.append('<h2 id="non-aperte">Pagine non controllate</h2><ul>')
        out += [f'<li>{escape(p["url"])}: {escape(p["error"])}</li>' for p in failed_pages]
        out.append("</ul>")

    out += [
        '<h2 id="criteri">Stato dei 55 criteri</h2>',
        "<table><caption>Criteri WCAG 2.2 di livello A e AA. Gli errori sono contati sui contenuti propri; "
        "quelli in contenuti di terzi (iframe di altre origini) sono a parte.</caption>",
        "<thead><tr><th scope='col'>Criterio</th><th scope='col'>Livello</th><th scope='col'>Fascia</th>"
        "<th scope='col'>EN 301 549 v3.2.1</th><th scope='col'>Stato</th><th scope='col'>Errori</th>"
        "<th scope='col'>Da verificare</th><th scope='col'>Di terzi</th></tr></thead><tbody>",
    ]
    for c in criteria:
        en = c["en301549_v3"] or "— (WCAG 2.2, non ancora obbligatorio)"
        out.append(
            f'<tr><th scope="row">{escape(c["id"])} {escape(c["title"])}</th><td>{c["level"]}</td>'
            f'<td>{_tier_label(c["tier"])}</td><td>{escape(en)}</td>'
            f'<td class="{_status_class(c["status"])}">{escape(c["status"])}</td>'
            f'<td>{c["failed"]}</td><td>{c["cant_tell"]}</td><td>{c["third_party"]}</td></tr>'
        )
    out.append("</tbody></table>")

    out.append('<h2 id="dettaglio">Dettaglio per pagina</h2>')
    by_page: dict[str, list[dict]] = {}
    for f in findings:
        by_page.setdefault(f["page_url"], []).append(f)
    for page in report["pages"]:
        items = by_page.get(page["url"], [])
        out.append(f'<h3>{escape(page["url"])}</h3>')
        for warning in page.get("warnings", []):
            out.append(f'<p class="note">Avviso: {escape(warning)}</p>')
        if not items:
            out.append("<p>Nessun errore e nessun elemento da verificare rilevati in automatico.</p>")
            continue
        out.append(
            "<table><thead><tr><th scope='col'>Criterio</th><th scope='col'>Esito</th>"
            "<th scope='col'>Regola</th><th scope='col'>Elemento</th><th scope='col'>Dettagli</th></tr></thead><tbody>"
        )
        for f in items:
            outcome = "errore" if f["outcome"] == "failed" else "da verificare"
            extra = []
            if f["third_party"]:
                extra.append("contenuto di terzi")
            if f.get("in_catalog") and not f.get("legally_required_now"):
                extra.append("WCAG 2.2, non ancora obbligatorio")
            if f["state"] != "iniziale":
                extra.append(f'stato: {f["state"]}')
            note = f' ({", ".join(extra)})' if extra else ""
            html_snippet = f["html"] if len(f["html"]) <= 300 else f["html"][:300] + "…"
            out.append(
                f'<tr><td>{escape(f["sc"])}</td><td>{outcome}{escape(note)}</td>'
                f'<td><a href="{escape(f["help_url"])}">{escape(f["rule_id"])}</a></td>'
                f'<td><code>{escape(f["selector"])}</code></td>'
                f'<td><details><summary>Mostra</summary><p><code>{escape(html_snippet)}</code></p>'
                f'<p>{escape(f["message"]).replace(chr(10), "<br>")}</p></details></td></tr>'
            )
        out.append("</tbody></table>")

    out.append("</main></body></html>")
    return "\n".join(out)


def write_html(report: dict, path: Path) -> None:
    path.write_text(render_html(report), encoding="utf-8")
