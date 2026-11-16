"""Upload validation, persistence, and duplicate rejection."""
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from web.server import create_app


def wav_bytes(path: Path, seconds: float = 1.0, freq: float = 220.0) -> bytes:
    sr = 16000
    t = np.arange(int(sr * seconds)) / sr
    signal = (0.3 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    sf.write(path, signal, sr)
    return path.read_bytes()


def test_upload_stores_one_merged_session(tmp_path):
    app = create_app(data_dir=tmp_path / "data", max_upload_bytes=5_000_000)
    client = TestClient(app)
    vowel = wav_bytes(tmp_path / "vowel.wav")
    passage = wav_bytes(tmp_path / "passage.wav", seconds=1.5)
    r = client.post(
        "/api/session",
        data={"subject": "AMANDA", "session": "day1"},
        files={
            "vowel": ("vowel.wav", vowel, "audio/wav"),
            "passage": ("passage.wav", passage, "audio/wav"),
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["subject"] == "AMANDA"
    assert body["session"] == "day1"
    assert set(body["features"]) >= {"f0_mean_hz", "jitter_local", "pause_ratio"}
    records = (tmp_path / "data" / "sessions.jsonl").read_text().splitlines()
    assert len(records) == 1
    assert (tmp_path / "data" / "recordings" / "AMANDA" / "day1_vowel.wav").exists()


def test_upload_rejects_non_wav(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path / "data"))
    r = client.post(
        "/api/session",
        data={"subject": "AMANDA", "session": "day1"},
        files={
            "vowel": ("vowel.webm", b"not a wav", "audio/webm"),
            "passage": ("passage.wav", wav_bytes(tmp_path / "p.wav"), "audio/wav"),
        },
    )
    assert r.status_code == 422


def test_upload_rejects_bad_subject(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path / "data"))
    wav = wav_bytes(tmp_path / "v.wav")
    r = client.post(
        "/api/session",
        data={"subject": "../etc", "session": "day1"},
        files={
            "vowel": ("v.wav", wav, "audio/wav"),
            "passage": ("p.wav", wav, "audio/wav"),
        },
    )
    assert r.status_code == 422


def test_upload_rejects_duplicate_session(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path / "data"))
    wav = wav_bytes(tmp_path / "v.wav")
    files = {
        "vowel": ("v.wav", wav, "audio/wav"),
        "passage": ("p.wav", wav, "audio/wav"),
    }
    assert client.post("/api/session", data={"subject": "AMANDA", "session": "day1"},
                       files=files).status_code == 201
    assert client.post("/api/session", data={"subject": "AMANDA", "session": "day1"},
                       files=files).status_code == 409


def test_upload_rejects_oversized_file(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path / "data", max_upload_bytes=100))
    wav = wav_bytes(tmp_path / "v.wav")
    r = client.post(
        "/api/session",
        data={"subject": "AMANDA", "session": "day1"},
        files={
            "vowel": ("v.wav", wav, "audio/wav"),
            "passage": ("p.wav", wav, "audio/wav"),
        },
    )
    assert r.status_code == 413


def test_replace_overwrites_session_and_drops_its_checkin(tmp_path):
    data = tmp_path / "data"
    client = TestClient(create_app(data_dir=data, max_upload_bytes=5_000_000))

    def post(freq, **extra):
        return client.post(
            "/api/session",
            data={"subject": "AMANDA", "session": "day1", **extra},
            files={
                "vowel": ("vowel.wav", wav_bytes(tmp_path / "v.wav", freq=freq), "audio/wav"),
                "passage": ("passage.wav", wav_bytes(tmp_path / "p.wav", 1.5, freq), "audio/wav"),
            },
        )

    first = post(220.0)
    assert first.status_code == 201, first.text
    ctx = client.post("/api/context", json={
        "subject": "AMANDA", "session": "day1",
        "answers": {"cold_or_congestion": True}})
    assert ctx.status_code == 201, ctx.text

    assert post(150.0).status_code == 409                 # no silent overwrite
    redo = post(150.0, replace="true")
    assert redo.status_code == 201, redo.text

    sessions = (data / "sessions.jsonl").read_text().splitlines()
    assert len(sessions) == 1                              # replaced, not appended
    assert abs(redo.json()["features"]["f0_mean_hz"] - 150.0) < 5
    context = (data / "context.jsonl").read_text().strip()
    assert context == ""                                   # old answers do not carry over


def test_sessions_are_timestamped_and_next_flight_day_is_suggested(tmp_path):
    from datetime import datetime

    data = tmp_path / "data"
    client = TestClient(create_app(data_dir=data, max_upload_bytes=5_000_000))
    assert client.get("/api/next-session", params={"subject": "AMANDA"}).json()["flight_day"] == 1

    def post(session):
        return client.post(
            "/api/session", data={"subject": "AMANDA", "session": session},
            files={"vowel": ("v.wav", wav_bytes(tmp_path / "v.wav"), "audio/wav"),
                   "passage": ("p.wav", wav_bytes(tmp_path / "p.wav", 1.5), "audio/wav")})

    first = post("fd1")
    assert first.status_code == 201, first.text
    stamp = datetime.fromisoformat(first.json()["recorded_at"])
    assert stamp.tzinfo is not None                      # carries its UTC offset
    assert client.get("/api/next-session", params={"subject": "AMANDA"}).json()["session"] == "fd2"

    # Older "dayN" labels still count, and a skipped day is not reused.
    assert post("day5").status_code == 201
    assert client.get("/api/next-session", params={"subject": "AMANDA"}).json()["flight_day"] == 6
    assert client.get("/api/next-session", params={"subject": "BOB"}).json()["flight_day"] == 1
    report = client.get("/api/report", params={"subject": "AMANDA"}).json()
    assert len(report["recorded_at"]) == 2 and all(report["recorded_at"])


def test_delete_removes_measurements_checkin_and_audio(tmp_path):
    data = tmp_path / "data"
    client = TestClient(create_app(data_dir=data, max_upload_bytes=5_000_000))

    def post(session):
        return client.post(
            "/api/session", data={"subject": "AMANDA", "session": session},
            files={"vowel": ("v.wav", wav_bytes(tmp_path / "v.wav"), "audio/wav"),
                   "passage": ("p.wav", wav_bytes(tmp_path / "p.wav", 1.5), "audio/wav")})

    assert post("fd1").status_code == 201 and post("fd2").status_code == 201
    client.post("/api/context", json={"subject": "AMANDA", "session": "fd1",
                                      "answers": {"cough": True}})
    audio = data / "recordings" / "AMANDA"
    assert (audio / "fd1_vowel.wav").exists()

    gone = client.delete("/api/session", params={"subject": "AMANDA", "session": "fd1"})
    assert gone.status_code == 200 and gone.json()["audio_files_deleted"] == 2
    assert not (audio / "fd1_vowel.wav").exists() and not (audio / "fd1_passage.wav").exists()
    assert (audio / "fd2_vowel.wav").exists()                      # other sessions untouched
    sessions = (data / "sessions.jsonl").read_text()
    assert '"fd1"' not in sessions and '"fd2"' in sessions
    assert (data / "context.jsonl").read_text().strip() == ""
    assert client.get("/api/report", params={"subject": "AMANDA"}).json()["sessions"] == ["fd2"]

    again = client.delete("/api/session", params={"subject": "AMANDA", "session": "fd1"})
    assert again.status_code == 404
    bad = client.delete("/api/session", params={"subject": "../x", "session": "fd1"})
    assert bad.status_code == 422


def test_saved_session_can_be_opened_and_played_back(tmp_path):
    data = tmp_path / "data"
    client = TestClient(create_app(data_dir=data, max_upload_bytes=5_000_000))
    made = client.post(
        "/api/session", data={"subject": "AMANDA", "session": "fd1"},
        files={"vowel": ("v.wav", wav_bytes(tmp_path / "v.wav"), "audio/wav"),
               "passage": ("p.wav", wav_bytes(tmp_path / "p.wav", 1.5), "audio/wav")})
    assert made.status_code == 201
    client.post("/api/context", json={"subject": "AMANDA", "session": "fd1",
                                      "raw": {"cough": "yes"}})
    where = {"subject": "AMANDA", "session": "fd1"}

    info = client.get("/api/session-detail", params=where).json()
    assert info["takes"] == ["vowel", "passage"]
    assert len(info["measures"]) == 8 and all(m["value_text"] for m in info["measures"])
    assert any(item["answer"] == "yes" for item in info["checkin"])

    audio = client.get("/api/audio", params={**where, "take": "vowel"})
    assert audio.status_code == 200 and audio.content[:4] == b"RIFF"
    assert client.get("/api/audio", params={**where, "take": "free"}).status_code == 404
    assert client.get("/api/audio", params={**where, "take": "../x"}).status_code == 422
    assert client.get("/api/session-detail",
                      params={"subject": "AMANDA", "session": "fd9"}).status_code == 404


def test_hosted_demo_keeps_visitors_apart_and_expires(tmp_path):
    data = tmp_path / "data"
    app = create_app(data_dir=data, max_upload_bytes=5_000_000, hosted=True)
    files = lambda: {  # noqa: E731
        "vowel": ("v.wav", wav_bytes(tmp_path / "v.wav"), "audio/wav"),
        "passage": ("p.wav", wav_bytes(tmp_path / "p.wav", 1.5), "audio/wav")}

    first = TestClient(app, base_url="https://testserver")
    made = first.post("/api/session", data={"subject": "GUEST", "session": "fd1"},
                      files=files())
    assert made.status_code == 201
    assert "bd_visitor" in first.cookies
    assert first.get("/api/report", params={"subject": "GUEST"}).json()["session_count"] == 1
    where = {"subject": "GUEST", "session": "fd1"}
    assert first.get("/api/audio", params={**where, "take": "vowel"}).status_code == 200

    second = TestClient(app, base_url="https://testserver")
    assert second.get("/api/report", params={"subject": "GUEST"}).json()["session_count"] == 0
    assert second.cookies["bd_visitor"] != first.cookies["bd_visitor"]
    assert second.get("/api/audio", params={**where, "take": "vowel"}).status_code == 404

    # Past retention, the next request from anyone sweeps the old space away.
    import os, time
    from web.server import RETENTION_SECONDS
    for folder in data.iterdir():
        old = time.time() - RETENTION_SECONDS - 60
        os.utime(folder / ".started", (old, old))
    app.user_middleware[0].kwargs["store"].last_sweep = 0
    TestClient(app, base_url="https://testserver").get("/")
    assert not list(data.rglob("*.wav")) and not list(data.rglob("sessions.jsonl"))
    assert "BASELINE_DRIFT_HOSTED" in second.get("/").text
    health = second.get("/api/health")
    assert health.json()["ok"] and health.headers["access-control-allow-origin"] == "*"


def test_local_app_is_not_hosted(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path / "data"))
    page = client.get("/")
    assert "BASELINE_DRIFT_HOSTED = " not in page.text and "set-cookie" not in page.headers


def test_baseline_can_start_at_a_chosen_session(tmp_path):
    data = tmp_path / "data"
    client = TestClient(create_app(data_dir=data, max_upload_bytes=5_000_000))
    for day in range(1, 6):
        made = client.post(
            "/api/session", data={"subject": "AMANDA", "session": f"fd{day}"},
            files={"vowel": ("v.wav", wav_bytes(tmp_path / "v.wav"), "audio/wav"),
                   "passage": ("p.wav", wav_bytes(tmp_path / "p.wav", 1.5), "audio/wav")})
        assert made.status_code == 201
    report = client.get("/api/report", params={"subject": "AMANDA"}).json()
    assert report["sessions"][0] == "fd1" and not report["baseline_moved"]

    moved = client.post("/api/baseline", json={"subject": "AMANDA", "session": "fd3"})
    assert moved.status_code == 200
    report = client.get("/api/report", params={"subject": "AMANDA"}).json()
    assert report["sessions"] == ["fd3", "fd4", "fd5"]            # the new baseline
    assert [e["session"] for e in report["earlier"]] == ["fd1", "fd2"]
    assert report["baseline_moved"] and report["state"] == "baseline"
    assert report["total_sessions"] == 5                          # nothing was deleted

    assert client.post("/api/baseline",
                       json={"subject": "AMANDA", "session": "nope"}).status_code == 404

    # Deleting the chosen starting session falls back to the first sessions.
    client.delete("/api/session", params={"subject": "AMANDA", "session": "fd3"})
    report = client.get("/api/report", params={"subject": "AMANDA"}).json()
    assert report["sessions"][0] == "fd1" and not report["baseline_moved"]

    client.post("/api/baseline", json={"subject": "AMANDA", "session": "fd4"})
    client.post("/api/baseline", json={"subject": "AMANDA", "session": None})
    assert not client.get("/api/report", params={"subject": "AMANDA"}).json()["baseline_moved"]
