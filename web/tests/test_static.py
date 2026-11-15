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
