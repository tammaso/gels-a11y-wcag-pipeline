from collections import Counter

from a11y_pipeline.catalog import load_catalog, sort_key

NEW_IN_22 = {"2.4.11", "2.5.7", "2.5.8", "3.2.6", "3.3.7", "3.3.8"}


def test_catalog_has_55_criteria_a_and_aa():
    catalog = load_catalog()
    assert len(catalog) == 55
    assert Counter(c.level for c in catalog.values()) == {"A": 31, "AA": 24}


def test_obsolete_parsing_is_excluded():
    assert "4.1.1" not in load_catalog()


def test_versions():
    catalog = load_catalog()
    assert Counter(c.since for c in catalog.values()) == {"2.0": 37, "2.1": 12, "2.2": 6}
    assert {c.id for c in catalog.values() if c.since == "2.2"} == NEW_IN_22


def test_tiers_match_step_one_classification():
    catalog = load_catalog()
    assert Counter(c.tier for c in catalog.values()) == {1: 15, 2: 16, 3: 24}
    # Nessuno dei criteri nuovi della 2.2 ha regole ACT.
    assert all(catalog[sc].tier == 3 for sc in NEW_IN_22)


def test_en301549_clauses():
    catalog = load_catalog()
    assert catalog["1.1.1"].en301549_v3 == "9.1.1.1"
    assert catalog["1.4.12"].en301549_v3 == "9.1.4.12"
    assert catalog["2.5.8"].en301549_v3 is None
    assert catalog["2.5.8"].en301549_v4 == "9.2.5.8"
    assert sum(c.legally_required_now for c in catalog.values()) == 49


def test_catalog_is_in_wcag_order():
    ids = list(load_catalog())
    assert ids == sorted(ids, key=sort_key)


def test_understanding_url():
    assert load_catalog()["1.4.3"].url.endswith("/Understanding/contrast-minimum.html")
