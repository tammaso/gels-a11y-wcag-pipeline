"""Test della conversione dei risultati di axe nel formato comune (senza browser)."""

import pytest

from a11y_pipeline.engines import is_third_party
from a11y_pipeline.engines.axe import AxeEngine, normalize, sc_from_tag
from a11y_pipeline.models import Outcome

RAW = {
    "testEngine": {"name": "axe-core", "version": "4.14.1"},
    "violations": [
        {
            "id": "image-alt",
            "impact": "critical",
            "tags": ["cat.text-alternatives", "wcag2a", "wcag111", "EN-301-549", "EN-9.1.1.1", "ACT"],
            "helpUrl": "https://dequeuniversity.com/rules/axe/4.14/image-alt",
            "nodes": [
                {"target": ["img"], "html": '<img src="foto.png">', "failureSummary": "Manca alt"},
                {"target": [["my-gallery", "img.copertina"]], "html": "<img>", "failureSummary": "Manca alt"},
            ],
        },
        {
            "id": "link-name",
            "tags": ["wcag2a", "wcag244", "wcag412"],
            "helpUrl": "u",
            "nodes": [{"target": ["a"], "html": "<a></a>", "failureSummary": "Link senza nome"}],
        },
    ],
    "incomplete": [
        {
            "id": "color-contrast",
            "tags": ["wcag2aa", "wcag143"],
            "helpUrl": "u",
            "nodes": [
                {
                    "target": ["p"],
                    "html": "<p>",
                    "any": [{"message": "Sfondo con immagine: contrasto non determinabile"}],
                }
            ],
        }
    ],
}


@pytest.mark.parametrize(
    "tag, expected",
    [
        ("wcag111", "1.1.1"),
        ("wcag143", "1.4.3"),
        ("wcag1412", "1.4.12"),
        ("wcag2411", "2.4.11"),
        ("wcag258", "2.5.8"),
        ("wcag2a", None),
        ("wcag21aa", None),
        ("wcag22aa", None),
        ("wcag2a-obsolete", None),
        ("EN-9.1.1.1", None),
    ],
)
def test_sc_from_tag(tag, expected):
    assert sc_from_tag(tag) == expected


def test_normalize_one_finding_per_element_and_criterion():
    findings = normalize(RAW, page_url="https://x.it/p", state="iniziale", frame_url="https://x.it/p")
    assert [(f.rule_id, f.sc, f.outcome) for f in findings] == [
        ("image-alt", "1.1.1", Outcome.FAILED),
        ("image-alt", "1.1.1", Outcome.FAILED),
        ("link-name", "2.4.4", Outcome.FAILED),
        ("link-name", "4.1.2", Outcome.FAILED),
        ("color-contrast", "1.4.3", Outcome.CANT_TELL),
    ]
    assert findings[0].engine_version == "4.14.1"
    assert findings[1].selector == "my-gallery >> img.copertina"  # shadow DOM
    assert findings[4].message == "Sfondo con immagine: contrasto non determinabile"


def test_normalize_resolves_iframe_and_marks_third_party():
    raw = {
        "violations": [
            {
                "id": "image-alt",
                "tags": ["wcag111"],
                "nodes": [
                    {"target": ["img"], "html": "<img>"},
                    {"target": ["#video", "img"], "html": "<img>"},
                ],
            }
        ]
    }
    seen = []

    def frame_url_for(path):
        seen.append(path)
        return "https://video.example.com/embed"

    own, embedded = normalize(
        raw, page_url="https://x.it/p", state="s", frame_url="https://x.it/p", frame_url_for=frame_url_for
    )
    assert (own.frame_url, own.third_party) == ("https://x.it/p", False)
    assert (embedded.frame_url, embedded.third_party) == ("https://video.example.com/embed", True)
    assert embedded.selector == "#video >>> img"
    assert seen == [("#video",)]


def test_normalize_attaches_act_ids():
    findings = normalize(RAW, page_url="u", state="s", frame_url="u", act_ids={"image-alt": ("23a2a8",)})
    assert findings[0].act_rule_ids == ("23a2a8",)
    assert findings[2].act_rule_ids == ()


@pytest.mark.parametrize(
    "frame, page, expected",
    [
        ("https://a.it/x", "https://a.it/y", False),
        ("https://b.it/x", "https://a.it/y", True),
        ("about:srcdoc", "https://a.it/y", False),
        ("file:///tmp/a.html", "file:///tmp/b.html", False),
        ("https://www.youtube.com/embed/1", "file:///tmp/b.html", True),
    ],
)
def test_is_third_party(frame, page, expected):
    assert is_third_party(frame, page) is expected


def test_run_options_use_all_tags_up_to_22aa(tmp_path):
    axe_file = tmp_path / "axe.min.js"
    axe_file.write_text("")
    options = AxeEngine(axe_path=axe_file, enable_rules=["target-size"]).run_options()
    assert options["runOnly"] == {
        "type": "tag",
        "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"],
    }
    assert options["rules"] == {"target-size": {"enabled": True}}
    assert "iframes" not in options  # gli iframe sono gestiti con runPartial/finishRun
