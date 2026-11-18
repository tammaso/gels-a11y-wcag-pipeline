"""Riga di comando: ``a11y-check`` (oppure ``python -m a11y_pipeline``)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from a11y_pipeline import __version__
from a11y_pipeline.browser import BrowserOptions, BrowserSession, parse_viewport
from a11y_pipeline.engines import get_engine
from a11y_pipeline.report import blocking_findings, build_report, write_html, write_json
from a11y_pipeline.runner import check_pages, default_scenario, load_scenario
from a11y_pipeline.sources import resolve_targets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="a11y-check",
        description=(
            "Rileva errori di accessibilità rispetto a WCAG 2.2 A/AA e li collega "
            "alle clausole EN 301 549. Non certifica la conformità."
        ),
    )
    parser.add_argument(
        "targets",
        nargs="+",
        help="URL, sitemap (.xml), file o cartella HTML, oppure elenco .txt/.csv",
    )
    parser.add_argument("-o", "--out-dir", default="a11y-report", help="cartella dei report (default: a11y-report)")
    parser.add_argument("--engine", action="append", default=None, help="motore da usare (default: axe)")
    parser.add_argument("--viewport", default="1280x800", help="dimensione finestra, es. 320x640 (default: 1280x800)")
    parser.add_argument("--browser-channel", default=None, help='es. "chrome" per usare Google Chrome installato')
    parser.add_argument("--headed", action="store_true", help="mostra il browser durante il controllo")
    parser.add_argument("--settle-ms", type=int, default=500, help="attesa dopo il caricamento (default: 500)")
    parser.add_argument(
        "--click",
        action="append",
        default=[],
        metavar="SELETTORE",
        help="elemento da cliccare prima del controllo (es. il pulsante del banner cookie); ripetibile",
    )
    parser.add_argument("--scenario", help="file Python con run(page, check) per controllare più stati della pagina")
    parser.add_argument("--storage-state", help="file JSON con una sessione di login salvata da Playwright")
    parser.add_argument(
        "--enable-rule",
        action="append",
        default=[],
        metavar="REGOLA",
        help="attiva una regola axe sperimentale (es. css-orientation-lock); ripetibile",
    )
    parser.add_argument(
        "--disable-rule",
        action="append",
        default=[],
        metavar="REGOLA",
        help="disattiva una regola axe (es. target-size); ripetibile",
    )
    parser.add_argument(
        "--fail-on",
        choices=["errori", "errori-obbligatori", "nessuno"],
        default="errori",
        help=(
            "quando restituire codice di uscita 1: ogni errore (default), "
            "solo errori sui criteri richiesti dalla EN 301 549 v3.2.1, oppure mai"
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    urls = resolve_targets(args.targets)
    if not urls:
        print("Nessuna pagina da controllare.", file=sys.stderr)
        return 2

    engines = [
        get_engine(name, enable_rules=args.enable_rule, disable_rules=args.disable_rule)
        for name in (args.engine or ["axe"])
    ]
    scenario = load_scenario(args.scenario) if args.scenario else default_scenario
    options = BrowserOptions(
        viewport=parse_viewport(args.viewport),
        channel=args.browser_channel,
        headless=not args.headed,
        storage_state=args.storage_state,
        settle_ms=args.settle_ms,
        clicks=args.click,
    )

    def progress(index: int, total: int, url: str) -> None:
        print(f"[{index}/{total}] {url}", file=sys.stderr)

    with BrowserSession(options) as session:
        results = check_pages(session, urls, engines, scenario, progress)

    engines_info = [
        {"name": e.name, "version": e.version, "options": getattr(e, "run_options", lambda: {})()}
        for e in engines
    ]
    report = build_report(results, engines_info)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, out_dir / "report.json")
    write_html(report, out_dir / "report.html")

    blocking = blocking_findings([f for r in results for f in r.findings], args.fail_on)
    page_errors = [r for r in results if r.error]
    criteria_with_errors = sorted({f.sc for f in blocking})
    print(
        f"\nPagine: {len(results)} (non aperte: {len(page_errors)}) · "
        f"errori bloccanti: {len(blocking)} · criteri con errori: {', '.join(criteria_with_errors) or 'nessuno'}"
    )
    print(f"Report: {out_dir / 'report.html'} e {out_dir / 'report.json'}")
    if page_errors:
        return 2
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
