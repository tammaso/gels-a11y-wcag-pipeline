"""Regressione sui test case ufficiali ACT del W3C.

Per ogni test case di una regola ACT che axe-core dichiara di implementare, si eseguono
solo le regole axe collegate a quella regola ACT e si confronta l'esito con quello atteso.
È lo stesso criterio usato dal W3C per le pagine di implementazione:
https://www.w3.org/WAI/standards-guidelines/act/implementations/

- falso positivo: errore segnalato su un esempio "passed" o "inapplicable" -> il test fallisce
- mancato rilevamento: nessun errore su un esempio "failed" -> solo conteggiato nel riepilogo
  (gli strumenti automatici possono non coprire tutti gli esempi)

Esecuzione:  pytest -m act
Variabili d'ambiente (facoltative):
  ACT_TESTCASES   percorso o URL di testcases.json (default: copia ufficiale W3C)
  ACT_BASE_URL    sostituisce https://www.w3.org negli URL dei test case (copia locale)
  ACT_RULES       elenco di ID ACT separati da virgola, per limitare il controllo
  ACT_SUMMARY     dove scrivere il riepilogo JSON (default: reports/act-summary.json)
"""

from __future__ import annotations

import json
import os
import urllib.request
from collections import defaultdict
from pathlib import Path

import pytest
import yaml

from a11y_pipeline.engines.axe import AxeEngine
from a11y_pipeline.models import Outcome
from a11y_pipeline.runner import check_page

pytestmark = [pytest.mark.act, pytest.mark.browser, pytest.mark.network]

TESTCASES = os.environ.get(
    "ACT_TESTCASES", "https://www.w3.org/WAI/content-assets/wcag-act-rules/testcases.json"
)
KNOWN_DIFFERENCES = Path(__file__).with_name("known_differences.yaml")


def load_testcases() -> list[dict]:
    if TESTCASES.startswith("http"):
        with urllib.request.urlopen(TESTCASES, timeout=60) as response:
            return json.load(response)["testcases"]
    return json.loads(Path(TESTCASES).read_text("utf-8"))["testcases"]


def localize(url: str) -> str:
    base = os.environ.get("ACT_BASE_URL")
    return url.replace("https://www.w3.org", base.rstrip("/"), 1) if base else url


def axe_rules_by_act_id(browser_session, axe_path) -> dict[str, list[str]]:
    page = browser_session._context.new_page()  # pagina vuota solo per leggere i metadati di axe
    try:
        page.set_content("<!DOCTYPE html><html><body></body></html>")
        page.add_script_tag(path=str(axe_path))
        rules = page.evaluate("() => axe.getRules().map(r => ({id: r.ruleId, act: r.actIds || []}))")
    finally:
        page.close()
    mapping: dict[str, list[str]] = defaultdict(list)
    for rule in rules:
        for act_id in rule["act"]:
            mapping[act_id].append(rule["id"])
    return dict(mapping)


def test_no_false_positives_on_act_testcases(browser_session, axe_path):
    try:
        testcases = load_testcases()
    except OSError as exc:
        pytest.skip(f"testcases.json non raggiungibile: {exc}")

    mapping = axe_rules_by_act_id(browser_session, axe_path)
    only = {r.strip() for r in os.environ.get("ACT_RULES", "").split(",") if r.strip()}
    known = yaml.safe_load(KNOWN_DIFFERENCES.read_text("utf-8")) or {}
    known_ids = {item["testcaseId"] for item in known.get("false_positives", [])}

    engines: dict[str, AxeEngine] = {}
    stats: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    false_positives, misses, errors = [], [], []

    for case in testcases:
        act_id = case["ruleId"]
        if act_id not in mapping or (only and act_id not in only):
            continue
        if not case["url"].endswith(".html"):
            # Documenti SVG o XML: axe-core lavora su pagine HTML, il caso resta non testato.
            stats[act_id]["untested_non_html"] += 1
            continue
        engine = engines.setdefault(act_id, AxeEngine(only_rules=mapping[act_id], axe_path=axe_path))
        result = check_page(browser_session, localize(case["url"]), [engine])
        rule_stats = stats[act_id]
        rule_stats["name"] = case["ruleName"]
        if result.error:
            errors.append({"testcaseId": case["testcaseId"], "url": case["url"], "error": result.error})
            rule_stats["errors"] += 1
            continue
        outcomes = {f.outcome for f in result.findings}
        got = "failed" if Outcome.FAILED in outcomes else "cantTell" if Outcome.CANT_TELL in outcomes else "passed"
        expected = case["expected"]
        rule_stats[f"{expected}->{got}"] += 1
        record = {
            "ruleId": act_id,
            "ruleName": case["ruleName"],
            "testcaseId": case["testcaseId"],
            "url": case["url"],
            "axeRules": mapping[act_id],
        }
        if expected in ("passed", "inapplicable") and got == "failed":
            if case["testcaseId"] not in known_ids:
                false_positives.append(record)
        elif expected == "failed" and got == "passed":
            misses.append(record)

    summary_path = Path(os.environ.get("ACT_SUMMARY", "reports/act-summary.json"))
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(
            {
                "axe_version": next((e.version for e in engines.values() if e.version), None),
                "testcases_checked": sum(v for s in stats.values() for k, v in s.items() if "->" in k),
                "testcases_untested": sum(
                    v for s in stats.values() for k, v in s.items() if k in ("errors", "untested_non_html")
                ),
                "act_rules_checked": len(stats),
                "false_positives": false_positives,
                "misses": misses,
                "page_errors": errors,
                "by_rule": stats,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    assert stats, "Nessun test case collegato alle regole di axe-core"
    assert not false_positives, (
        f"{len(false_positives)} falsi positivi (dettagli in {summary_path}): "
        + ", ".join(f'{fp["ruleId"]}/{fp["testcaseId"]}' for fp in false_positives[:20])
    )
