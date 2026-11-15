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
