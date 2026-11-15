"""Static shell, health endpoint, and the offline-only audit."""
import re
from pathlib import Path

from fastapi.testclient import TestClient

from web.server import create_app

APP = Path(__file__).resolve().parents[1] / "app"


def client(tmp_path):
    return TestClient(create_app(data_dir=tmp_path / "data", static_dir=APP))


def test_health(tmp_path):
    r = client(tmp_path).get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "offline": True}


def test_index_is_served(tmp_path):
    r = client(tmp_path).get("/")
    assert r.status_code == 200
    assert "Baseline Drift" in r.text


def test_no_external_assets():
    network = re.compile(
        r'(?:src|href)\s*=\s*["\']https?://'
        r'|fetch\(\s*["\']https?://'
        r'|@import\s+(?:url\()?["\']?https?://'
        r'|fonts\.(?:googleapis|gstatic)\.com',
        re.I,
    )
    for name in ("index.html", "app.js", "styles.css"):
        text = (APP / name).read_text(encoding="utf-8")
        assert not network.search(text), name


def test_static_files_are_never_cached(tmp_path):
    c = client(tmp_path)
    for path in ("/", "/app.js", "/styles.css"):
        assert c.get(path).headers.get("cache-control") == "no-store", path


def test_privacy_notice_is_on_the_page(tmp_path):
    text = client(tmp_path).get("/").text
    assert "Private. For your personal use only." in text
    assert "Nothing is shared unless you choose to share it yourself." in text


def test_page_links_are_version_stamped(tmp_path):
    c = client(tmp_path)
    text = c.get("/").text
    script = re.search(r'src="(/app\.js\?v=\d+)"', text)
    style = re.search(r'href="(/styles\.css\?v=\d+)"', text)
    assert script and style
    assert c.get(script.group(1)).status_code == 200
    assert c.get(style.group(1)).status_code == 200


def test_sample_report_is_served_and_labelled(tmp_path):
    report = client(tmp_path).get("/sample_report.json").json()
    assert report["sample"] is True and report["subject"] == "SAMPLE"
    assert report["state"] == "findings" and len(report["recorded_at"]) == report["session_count"]


def test_online_preview_builds_and_matches_the_app(tmp_path):
    from web.build_static_demo import build

    out = build(tmp_path / "try")
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "window.BASELINE_DRIFT_STATIC = true" in html
    assert 'src="app.js"' in html and 'href="styles.css"' in html
    assert "Your voice is not measured or kept." in html
    for name in ("app.js", "styles.css", "sample_report.json"):
        assert (out / name).read_bytes() == (APP / name).read_bytes(), name
    # The committed preview must not fall behind the app it mirrors.
    committed = APP.parents[1] / "docs" / "try"
    for name in ("index.html", "app.js", "styles.css", "sample_report.json"):
        assert (committed / name).read_bytes() == (out / name).read_bytes(), name
