"""The explains map and raw-answer parsing must match the CLI check-in."""
import pytest
from fastapi.testclient import TestClient

from pipeline.checkin_agent import QUESTIONS, parse_plain
from web.context_builder import build_answers_from_raw, build_explains
from web.server import create_app
from web.session_store import append_record, read_records


def test_cold_licenses_voice_quality_and_pitch():
    explains = build_explains({"cold_or_congestion": True})
    assert set(explains["hnr_db"]) == {"cold_or_congestion"}
    assert "f0_mean_hz" in explains
    assert "pause_ratio" not in explains


def test_cough_does_not_license_rate():
    explains = build_explains({"cough": True})
    assert "hnr_db" in explains
    assert "voiced_rate_hz" not in explains


def test_short_sleep_licenses_rate_and_pausing():
    explains = build_explains({"sleep_hours": 4.0})
    assert set(explains["voiced_rate_hz"]) == {"sleep_hours"}
    assert "pause_ratio" in explains


def test_normal_sleep_licenses_nothing():
    assert build_explains({"sleep_hours": 7.0}) == {}


def test_unusual_pain_licenses_nothing():
    assert build_explains({"unusual_pain": "lower back, since this morning"}) == {}


def test_reclined_posture_licenses_pitch_and_pausing():
    explains = build_explains({"posture": "reclined on the couch"})
    assert "f0_mean_hz" in explains
    assert "pause_ratio" in explains


def test_sitting_posture_licenses_nothing():
    assert build_explains({"posture": "sitting"}) == {}


def test_setup_change_licenses_everything():
    explains = build_explains({"setup_changed": True})
    assert len(explains) == 8


def test_parity_with_cli_parser():
    answers = {q["field"]: parse_plain("yes", q["type"]) for q in QUESTIONS}
    explains = build_explains(answers)
    assert "hnr_db" in explains


def make_client(tmp_path):
    return TestClient(create_app(data_dir=tmp_path / "data"))


def post_raw(tmp_path, text):
    client = make_client(tmp_path)
    response = client.post("/api/context", json={
        "subject": "AMANDA", "session": "day1",
        "raw": {"cold_or_congestion": text},
    })
    assert response.status_code == 201, response.text
    return read_records(tmp_path / "data" / "context.jsonl")[-1]


@pytest.mark.parametrize("text, expected", [
    ("a bit stuffy", True),
    ("slightly", True),
    ("negative", False),
    ("fine", False),
    ("not sure", None),
    ("", None),
    (None, None),
])
def test_raw_answers_use_the_cli_parser(tmp_path, text, expected):
    record = post_raw(tmp_path, text)
    answers = record["answers"]
    assert answers["cold_or_congestion"] is expected
    assert answers["cold_or_congestion_raw"] == (
        text.strip() if isinstance(text, str) and text.strip() else None)


def test_raw_answers_store_parsed_and_raw_entries_for_every_question(tmp_path):
    answers = post_raw(tmp_path, "a bit stuffy")["answers"]
    for question in QUESTIONS:
        assert question["field"] in answers
        assert question["field"] + "_raw" in answers


def test_raw_cold_answer_licenses_voice_quality(tmp_path):
    record = post_raw(tmp_path, "a bit stuffy")
    assert record["answers"]["cold_or_congestion"] is True
    assert record["explains"]["hnr_db"] == ["cold_or_congestion"]


def test_raw_inverted_setup_answer_is_parsed_by_question_type(tmp_path):
    client = make_client(tmp_path)
    response = client.post("/api/context", json={
        "subject": "AMANDA", "session": "day1",
        "raw": {"setup_changed": "no"},
    })
    assert response.status_code == 201, response.text
    record = read_records(tmp_path / "data" / "context.jsonl")[-1]
    assert record["answers"]["setup_changed"] is True
    assert "hnr_db" in record["explains"]


def test_structured_answers_remain_accepted_without_raw(tmp_path):
    client = make_client(tmp_path)
    response = client.post("/api/context", json={
        "subject": "AMANDA", "session": "day1",
        "answers": {"cold_or_congestion": True},
    })
    assert response.status_code == 201, response.text
    record = read_records(tmp_path / "data" / "context.jsonl")[-1]
    assert record["answers"] == {"cold_or_congestion": True}
    assert record["explains"]["hnr_db"] == ["cold_or_congestion"]


def test_raw_answers_must_be_strings_or_null(tmp_path):
    client = make_client(tmp_path)
    response = client.post("/api/context", json={
        "subject": "AMANDA", "session": "day1",
        "raw": {"cold_or_congestion": True},
    })
    assert response.status_code == 422


def test_build_answers_from_raw_rejects_non_string_values():
    with pytest.raises(ValueError):
        build_answers_from_raw({"cold_or_congestion": 1})


def test_raw_cold_answer_explains_a_report_finding(tmp_path):
    data = tmp_path / "data"
    client = TestClient(create_app(data_dir=data))
    feature_names = (
        "duration_s", "f0_mean_hz", "f0_sd_hz", "intensity_db",
        "jitter_local", "shimmer_local", "hnr_db", "pause_ratio",
        "voiced_rate_hz",
    )
    for session, hnr in [
        ("day1", 20.0), ("day2", 20.2), ("day3", 19.8),
        ("day4", 15.0), ("day5", 14.6),
    ]:
        features = {name: None for name in feature_names}
        features["hnr_db"] = hnr
        append_record(data / "sessions.jsonl", {
            "subject": "AMANDA", "session": session, "features": features,
        })

    response = client.post("/api/context", json={
        "subject": "AMANDA", "session": "day5",
        "raw": {"cold_or_congestion": "a bit stuffy"},
    })
    assert response.status_code == 201, response.text

    report = client.get("/api/report", params={"subject": "AMANDA"}).json()
    row = next(f for f in report["findings"] if f["feature"] == "hnr_db")
    assert row["explained"] == ["cold_or_congestion"]
