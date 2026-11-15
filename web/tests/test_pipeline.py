"""The detector's contract with its callers: two values, findings always a list.

The empty-findings branch used to return a nested tuple because a conditional
expression wrapped the whole return. These tests pin the shape so a caller
never has to normalise it again.
"""
from pipeline.voice_drift import analyse

FEATURES = (
    "duration_s", "f0_mean_hz", "f0_sd_hz", "intensity_db",
    "jitter_local", "shimmer_local", "hnr_db", "pause_ratio", "voiced_rate_hz",
)


def record(session, **overrides):
    """One session record with every feature present; overrides set the moves."""
    features = {name: None for name in FEATURES}
    features.update(overrides)
    return {"subject": "AMANDA", "session": session, "features": features}


def baseline():
    return [
        record("day1", intensity_db=84.0),
        record("day2", intensity_db=85.0),
        record("day3", intensity_db=86.0),
    ]


def test_no_findings_returns_a_flat_pair():
    stats, findings = analyse(baseline() + [record("day4", intensity_db=85.0)], 3, 2.0)
    assert isinstance(stats, dict) and "intensity_db" in stats
    assert isinstance(findings, list)
    assert findings == []


def test_a_sustained_move_returns_a_list_of_findings():
    records = baseline() + [
        record("day4", intensity_db=70.0),
        record("day5", intensity_db=69.0),
    ]
    _, findings = analyse(records, 3, 2.0)
    assert isinstance(findings, list)
    assert len(findings) == 2
    assert {f["feature"] for f in findings} == {"intensity_db"}
    assert {f["run_length"] for f in findings} == {2}


def test_short_baseline_returns_none_and_an_empty_list():
    stats, findings = analyse(baseline()[:2], 3, 2.0)
    assert stats is None
    assert findings == []
