from a11y_pipeline.models import Finding, Outcome, PageResult, ScStatus
from a11y_pipeline.report import blocking_findings, build_report, render_html, summarize, unique


def make(sc, outcome=Outcome.FAILED, *, state="iniziale", third_party=False, selector="img", rule="r"):
    return Finding(
        page_url="https://x.it/p",
        state=state,
        frame_url="https://x.it/p",
        third_party=third_party,
        engine="axe-core",
        engine_version="4.14.1",
        rule_id=rule,
        outcome=outcome,
        sc=sc,
        selector=selector,
        html="<img>",
        message="m",
        help_url="https://example.org",
    )


def statuses(findings):
    return {s.criterion.id: s.status for s in summarize(findings)}


def test_status_without_findings_depends_on_tier():
    s = statuses([])
    assert s["1.1.1"] is ScStatus.NO_ERRORS  # fascia 1
    assert s["2.4.7"] is ScStatus.MANUAL_CHECK  # fascia 2
    assert s["4.1.3"] is ScStatus.NOT_AUTOMATABLE  # fascia 3
    assert ScStatus.ERRORS not in s.values()


def test_errors_and_review():
    s = statuses([make("1.1.1"), make("1.4.3", Outcome.CANT_TELL)])
    assert s["1.1.1"] is ScStatus.ERRORS
    assert s["1.4.3"] is ScStatus.TO_REVIEW


def test_third_party_findings_do_not_change_status():
    summary = {x.criterion.id: x for x in summarize([make("1.1.1", third_party=True)])}
    assert summary["1.1.1"].status is ScStatus.NO_ERRORS
    assert summary["1.1.1"].third_party == 1


def test_same_problem_in_two_states_counted_once():
    findings = [make("1.1.1", state="iniziale"), make("1.1.1", state="aperto")]
    assert len(unique(findings)) == 1


def test_blocking_modes():
    findings = [
        make("1.1.1"),
        make("2.5.8", selector="button"),  # WCAG 2.2: non ancora obbligatorio
        make("1.4.3", Outcome.CANT_TELL),
        make("4.1.2", third_party=True),
    ]
    assert {f.sc for f in blocking_findings(findings, "errori")} == {"1.1.1", "2.5.8"}
    assert {f.sc for f in blocking_findings(findings, "errori-obbligatori")} == {"1.1.1"}
    assert blocking_findings(findings, "nessuno") == []


def test_report_structure_and_html():
    result = PageResult(url="https://x.it/p", states=["iniziale"], findings=[make("1.1.1"), make("2.5.8")])
    report = build_report([result], [{"name": "axe-core", "version": "4.14.1"}])
    assert report["legal_reference"] == "EN 301 549 v3.2.1"
    assert len(report["criteria"]) == 55
    by_sc = {f["sc"]: f for f in report["findings"]}
    assert by_sc["1.1.1"]["en301549_v3"] == "9.1.1.1"
    assert by_sc["2.5.8"]["legally_required_now"] is False
    html = render_html(report)
    assert '<html lang="it">' in html
    assert html.count('<th scope="row">') == 55
    assert "non ancora obbligatorio" in html
