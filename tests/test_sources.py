import pytest

from a11y_pipeline.sources import resolve_targets

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.example.it/a.html</loc></url>
  <url><loc>https://www.example.it/b.html</loc></url>
</urlset>"""


def test_url_passes_through():
    assert resolve_targets(["https://www.example.it/"]) == ["https://www.example.it/"]


def test_directory_collects_html_files(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.html").write_text("x")
    (tmp_path / "sub" / "b.htm").write_text("x")
    (tmp_path / "note.txt").write_text("x")
    targets = resolve_targets([str(tmp_path)])
    assert [t.rsplit("/", 1)[-1] for t in targets] == ["a.html", "b.htm"]
    assert all(t.startswith("file://") for t in targets)


def test_list_files_and_deduplication(tmp_path):
    txt = tmp_path / "pagine.txt"
    txt.write_text("# commento\nhttps://www.example.it/a.html\n\nhttps://www.example.it/a.html\n")
    csv = tmp_path / "pagine.csv"
    csv.write_text("https://www.example.it/b.html,nota\n")
    assert resolve_targets([str(txt), str(csv)]) == [
        "https://www.example.it/a.html",
        "https://www.example.it/b.html",
    ]


def test_local_sitemap(tmp_path):
    sitemap = tmp_path / "sitemap.xml"
    sitemap.write_text(SITEMAP)
    assert resolve_targets([str(sitemap)]) == [
        "https://www.example.it/a.html",
        "https://www.example.it/b.html",
    ]


def test_missing_input(tmp_path):
    with pytest.raises(FileNotFoundError):
        resolve_targets([str(tmp_path / "manca.html")])
