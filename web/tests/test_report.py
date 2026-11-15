"""Report JSON states, ordering, and context attachment."""
from web.reporting import build_report


def record(session, **features):
    base = {k: None for k in (
        "duration_s", "f0_mean_hz", "f0_sd_hz", "intensity_db",
        "jitter_local", "shimmer_local", "hnr_db", "pause_ratio",
        "voiced_rate_hz")}
    base.update(features)
    return {"subject": "AMANDA", "session": session, "features": base}


def baseline_records():
    return [
        record("day1", intensity_db=84.0, pause_ratio=0.050, f0_mean_hz=120.0),
        record("day2", intensity_db=85.0, pause_ratio=0.060, f0_mean_hz=121.0),
        record("day3", intensity_db=86.0, pause_ratio=0.055, f0_mean_hz=119.0),
    ]


def test_empty_state():
    report = build_report([], {}, "AMANDA")
    assert report["state"] == "empty"
    assert report["findings"] == []


def test_baseline_state_reports_progress():
    report = build_report(baseline_records()[:2], {}, "AMANDA")
    assert report["state"] == "baseline"
    assert report["baseline_progress"] == {"have": 2, "need": 3}


def test_three_sessions_complete_the_baseline_without_scoring():
    report = build_report(baseline_records(), {}, "AMANDA")
    assert report["state"] == "baseline"
    assert report["baseline_progress"] == {"have": 3, "need": 3}
    assert "Baseline complete" in report["headline"]
    assert report["findings"] == []


def test_stable_state_when_nothing_moves():
    records = baseline_records() + [
        record("day4", intensity_db=85.0, pause_ratio=0.055, f0_mean_hz=120.0),
    ]
    report = build_report(records, {}, "AMANDA")
    assert report["state"] == "stable"
    assert report["findings"] == []


def test_four_sessions_without_a_sustained_finding_are_stable():
    # One isolated move must not survive the two-session persistence gate.
    records = baseline_records() + [
        record("day4", intensity_db=70.0, pause_ratio=0.055, f0_mean_hz=120.0),
    ]
    report = build_report(records, {}, "AMANDA")
    assert report["state"] == "stable"
    assert report["findings"] == []


def test_unexplained_findings_come_first():
    records = baseline_records() + [
        record("day4", intensity_db=80.0, pause_ratio=0.120, f0_mean_hz=120.0),
        record("day5", intensity_db=79.5, pause_ratio=0.130, f0_mean_hz=120.5),
    ]
    context = {("AMANDA", "day5"): {"intensity_db": ["cold_or_congestion"]}}
    report = build_report(records, context, "AMANDA")
    assert report["state"] == "findings"
    first = report["findings"][0]
    assert first["feature"] == "pause_ratio"
    assert first["explained"] == []
    explained = [f for f in report["findings"] if f["feature"] == "intensity_db"][0]
    assert explained["explained"] == ["cold_or_congestion"]


def test_measures_are_reported_with_numbers_in_every_state():
    building = build_report(baseline_records()[:2], {}, "AMANDA")
    loud = next(m for m in building["measures"] if m["feature"] == "intensity_db")
    assert loud["latest_text"] == "85.0 dB" and loud["baseline_complete"] is False

    records = baseline_records() + [
        record("day4", intensity_db=85.2, pause_ratio=0.056, f0_mean_hz=120.2)]
    stable = build_report(records, {}, "AMANDA")
    assert stable["state"] == "stable"
    loud = next(m for m in stable["measures"] if m["feature"] == "intensity_db")
    assert loud["series"] == [84.0, 85.0, 86.0, 85.2]
    assert loud["baseline_text"] == "85.0 dB" and loud["spread_text"] == "1.0 dB"
    assert loud["change_text"] == "0.2 dB above your baseline"
    assert loud["flagged"] is False and loud["hint"]
    pause = next(m for m in stable["measures"] if m["feature"] == "pause_ratio")
    assert pause["latest_text"] == "5.6%"
    # A measure with no data is listed as not measured, never dropped silently.
    jitter = next(m for m in stable["measures"] if m["feature"] == "jitter_local")
    assert jitter["latest_text"] == "not measured"
