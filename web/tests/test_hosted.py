"""Hosted demo mode: visitor isolation, cookie scoping, and retention.

Every visitor gets a private folder keyed by a random cookie, and the sweep is
the only thing that deletes it. These tests pin both halves: one visitor can
never see another's data, and stale or excess spaces do get removed.
"""
import os
import time

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

import web.server as server
from web.server import create_app

BASE = "https://testserver"


def wav_bytes(path):
    """A short valid WAV, enough for the real extractor to run."""
    sr = 16000
    t = np.arange(int(sr * 0.5)) / sr
    sf.write(path, (0.3 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32), sr)
    return path.read_bytes()


def client_for(app):
    """A client that behaves like the production HTTPS deployment for cookies."""
    return TestClient(app, base_url=BASE)


def visitor_folder(tmp_path, client):
    return tmp_path / "data" / client.cookies.get(server.VISITOR_COOKIE)


def upload(client, tmp_path, subject="AMANDA", session="day1"):
    wav = wav_bytes(tmp_path / f"{session}.wav")
    return client.post(
        "/api/session",
        data={"subject": subject, "session": session},
        files={
            "vowel": ("v.wav", wav, "audio/wav"),
            "passage": ("p.wav", wav, "audio/wav"),
        },
    )


def test_each_visitor_gets_a_private_space(tmp_path):
    """Uploads in one browser never appear in another browser's report."""
    app = create_app(data_dir=tmp_path / "data", hosted=True)
    alice, bob = client_for(app), client_for(app)
    alice.get("/api/health")
    bob.get("/api/health")
    assert alice.cookies.get(server.VISITOR_COOKIE) != bob.cookies.get(server.VISITOR_COOKIE)

    assert upload(alice, tmp_path).status_code == 201

    assert alice.get("/api/report?subject=AMANDA").json()["session_count"] == 1
    assert bob.get("/api/report?subject=AMANDA").json()["session_count"] == 0
    assert bob.get("/api/session-detail?subject=AMANDA&session=day1").status_code == 404

    alice_dir = visitor_folder(tmp_path, alice)
    bob_dir = visitor_folder(tmp_path, bob)
    assert (alice_dir / "recordings" / "AMANDA" / "day1_vowel.wav").exists()
    assert not (bob_dir / "recordings" / "AMANDA").exists()


def test_the_cookie_is_random_scoped_and_sticky(tmp_path):
    """The first response sets one hardened cookie; later requests reuse it."""
    app = create_app(data_dir=tmp_path / "data", hosted=True)
    client = client_for(app)
    first = client.get("/api/health")
    cookie = first.headers.get("set-cookie", "")
    assert cookie.count(server.VISITOR_COOKIE) == 1
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert f"Max-Age={server.RETENTION_SECONDS}" in cookie
    assert server.VISITOR_RE.match(client.cookies.get(server.VISITOR_COOKIE))

    second = client.get("/api/health")
    assert second.headers.get("set-cookie") is None
    assert second.json() == first.json()


def test_a_malformed_cookie_is_replaced(tmp_path):
    """A cookie that fails the pattern gets a fresh visitor, not a crash."""
    app = create_app(data_dir=tmp_path / "data", hosted=True)
    client = client_for(app)
    response = client.get("/api/health", headers={"cookie": f"{server.VISITOR_COOKIE}=bad"})
    assert response.status_code == 200
    assert response.headers.get("set-cookie", "").count(server.VISITOR_COOKIE) == 1


def test_expired_spaces_are_deleted_by_the_sweep(tmp_path):
    """A space older than the retention window is removed on the next sweep."""
    app = create_app(data_dir=tmp_path / "data", hosted=True)
    old = client_for(app)
    old.get("/api/report?subject=AMANDA")
    old_dir = visitor_folder(tmp_path, old)
    assert old_dir.exists()
    marker = old_dir / ".started"
    stale = time.time() - server.RETENTION_SECONDS - 60
    os.utime(marker, (stale, stale))

    app.state.visitor_store.last_sweep = 0.0
    fresh = client_for(app)
    fresh.get("/api/health")
    assert not old_dir.exists()


def test_the_visitor_cap_deletes_the_oldest_spaces(tmp_path, monkeypatch):
    """Past the cap, the oldest spaces go first and recent ones stay."""
    monkeypatch.setattr(server, "MAX_VISITORS", 2)
    app = create_app(data_dir=tmp_path / "data", hosted=True)
    base = tmp_path / "data"
    now = time.time()
    names = ["a" * 20, "b" * 20, "c" * 20]
    for offset, name in enumerate(names):
        folder = base / name
        folder.mkdir()
        marker = folder / ".started"
        marker.touch()
        stamp = now - 300 + offset * 10
        os.utime(marker, (stamp, stamp))

    app.state.visitor_store.last_sweep = 0.0
    client_for(app).get("/api/health", headers={"cookie": f"{server.VISITOR_COOKIE}={names[1]}"})

    assert not (base / names[0]).exists()
    assert (base / names[1]).exists() and (base / names[2]).exists()


def test_hosted_health_is_readable_from_the_wake_page(tmp_path):
    """The GitHub Pages wake page polls this cross-origin, so CORS is explicit."""
    app = create_app(data_dir=tmp_path / "data", hosted=True)
    response = client_for(app).get("/api/health")
    assert response.json() == {"ok": True, "offline": False}
    assert response.headers["access-control-allow-origin"] == "*"
    assert response.headers["cache-control"] == "no-store"


def test_local_mode_is_offline_and_sets_no_cookie(tmp_path):
    """Without hosted mode the health check says offline and no visitor cookie exists."""
    app = create_app(data_dir=tmp_path / "data", hosted=False)
    response = TestClient(app).get("/api/health")
    assert response.json() == {"ok": True, "offline": True}
    assert response.headers.get("set-cookie") is None
    assert app.state.visitor_store is None
