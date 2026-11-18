"""Confronta il catalogo con i dati ufficiali W3C (WCAG 2.2 in JSON, aggiornato ogni mese).

Fonte: https://www.w3.org/WAI/WCAG22/wcag.json
(https://github.com/w3c/wcag/tree/main/11ty/json — W3C Document License).
"""

import json
import os
import urllib.request

import pytest

from a11y_pipeline.catalog import load_catalog

pytestmark = pytest.mark.network

WCAG_JSON = os.environ.get("WCAG_JSON", "https://www.w3.org/WAI/WCAG22/wcag.json")


@pytest.fixture(scope="module")
def official_criteria():
    try:
        if WCAG_JSON.startswith("http"):
            with urllib.request.urlopen(WCAG_JSON, timeout=30) as response:
                data = json.load(response)
        else:
            with open(WCAG_JSON, encoding="utf-8") as handle:
                data = json.load(handle)
    except OSError as exc:
        pytest.skip(f"WCAG JSON non raggiungibile: {exc}")
    return {
        sc["num"]: sc
        for principle in data["principles"]
        for guideline in principle["guidelines"]
        for sc in guideline["successcriteria"]
    }


def test_same_a_and_aa_criteria(official_criteria):
    official = {num for num, sc in official_criteria.items() if sc["level"] in ("A", "AA")}
    assert official == set(load_catalog())


def test_same_levels_and_titles(official_criteria):
    for sc_id, criterion in load_catalog().items():
        official = official_criteria[sc_id]
        assert official["level"] == criterion.level, sc_id
        assert official["handle"] == criterion.title, sc_id
