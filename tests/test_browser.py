"""Test di integrazione: browser vero + axe-core su pagine di prova con errori noti."""

import pytest

from a11y_pipeline.catalog import load_catalog
from a11y_pipeline.engines.axe import AxeEngine
from a11y_pipeline.models import Outcome
from a11y_pipeline.runner import check_page, load_scenario

from .conftest import FIXTURES, page_uri

pytestmark = pytest.mark.browser


def failed_criteria(result):
    return {f.sc for f in result.findings if f.outcome is Outcome.FAILED}


def test_page_with_known_errors(browser_session):
    result = check_page(browser_session, page_uri("errori.html"), [AxeEngine()])
    assert result.error is None
    assert {"1.1.1", "1.4.3", "1.4.4", "2.4.2", "2.4.4", "3.1.1", "4.1.2"} <= failed_criteria(result)
    # target-size è disattivata di default in axe-core, ma l'etichetta wcag22aa la attiva:
    # è l'unica regola axe per un criterio nuovo della 2.2 (2.5.8, non ancora obbligatorio).
    assert "2.5.8" in failed_criteria(result)
    assert load_catalog()["2.5.8"].legally_required_now is False


def test_rule_can_be_disabled(browser_session):
    result = check_page(browser_session, page_uri("errori.html"), [AxeEngine(disable_rules=["target-size"])])
    assert "2.5.8" not in failed_criteria(result)


def test_page_without_detectable_errors(browser_session):
    result = check_page(browser_session, page_uri("corretta.html"), [AxeEngine()])
    assert result.error is None
    assert failed_criteria(result) == set()


def test_scenario_checks_hidden_content(browser_session):
    scenario = load_scenario(FIXTURES / "scenario_accordion.py")
    result = check_page(browser_session, page_uri("accordion.html"), [AxeEngine()], scenario)
    assert result.states == ["iniziale", "pannello aperto"]
    image_errors = [f for f in result.findings if f.rule_id == "image-alt"]
    assert image_errors and {f.state for f in image_errors} == {"pannello aperto"}


def test_unreachable_page_is_reported_not_raised(browser_session):
    result = check_page(browser_session, page_uri("non-esiste.html"), [AxeEngine()])
    assert result.error


def test_iframe_of_other_origin_is_checked_and_marked_third_party(browser_session, two_origins):
    own_dir, own_url, other_dir, other_url = two_origins
    (other_dir / "embed.html").write_text(
        '<!DOCTYPE html><html lang="en"><title>Embed</title><img src="x.png"></html>'
    )
    (own_dir / "index.html").write_text(
        '<!DOCTYPE html><html lang="it"><title>Pagina</title><main><h1>Pagina</h1>'
        f'<iframe src="{other_url}/embed.html" title="Contenuto incorporato"></iframe></main></html>'
    )
    result = check_page(browser_session, f"{own_url}/index.html", [AxeEngine()])
    image_errors = [f for f in result.findings if f.rule_id == "image-alt"]
    assert len(image_errors) == 1
    assert image_errors[0].third_party is True
    assert image_errors[0].frame_url.startswith(other_url)
