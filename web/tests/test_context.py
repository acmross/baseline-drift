"""The explains map must match the rules the CLI check-in already uses."""
from pipeline.checkin_agent import QUESTIONS, parse_plain
from web.context_builder import build_explains


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


def test_headache_licenses_nothing():
    assert build_explains({"headache": True}) == {}


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
