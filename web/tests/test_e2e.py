"""Six synthetic sessions: three baseline, three drifting, one report."""
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from pipeline.make_test_audio import utterance
from web.server import create_app

PLAN = [
    ("day1", 118, 0.80, 0.010, 0.15),
    ("day2", 121, 0.82, 0.011, 0.17),
    ("day3", 119, 0.79, 0.010, 0.14),
    ("day4", 104, 0.55, 0.019, 0.42),
    ("day5", 102, 0.52, 0.021, 0.45),
    ("day6", 105, 0.54, 0.020, 0.40),
]


def wav(tmp_path: Path, name: str, args) -> bytes:
    path = tmp_path / name
    sf.write(path, utterance(*args[1:]), 16000)
    return path.read_bytes()


def test_three_baseline_sessions_then_drift_report(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path / "data"))
    for session, f0, amp, jitter, pause in PLAN:
        blob = wav(tmp_path, f"{session}.wav", (session, f0, amp, jitter, pause))
        response = client.post(
            "/api/session",
            data={"subject": "AMANDA", "session": session},
            files={
                "vowel": (f"{session}_vowel.wav", blob, "audio/wav"),
                "passage": (f"{session}_passage.wav", blob, "audio/wav"),
            },
        )
        assert response.status_code == 201, response.text

    report = client.get("/api/report", params={"subject": "AMANDA"}).json()
    assert report["state"] == "findings"
    assert report["session_count"] == 6
    assert len(report["findings"]) >= 1
    text = (report["headline"] + " " + " ".join(f["phrase"] for f in report["findings"])).lower()
    for banned in ("fatigue", "stressed", "diagnosis", "normal range"):
        assert banned not in text
