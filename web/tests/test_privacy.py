"""The published real dataset carries dates, not clock times or a full name.

A real recording's timestamp includes the laptop's timezone and the minute it
was made. Neither is needed to read the report, so the public copy keeps the
day only unless someone explicitly asks for times.
"""
import json
from pathlib import Path

from web.make_real_report import build, public_stamp

ROOT = Path(__file__).resolve().parents[2]


def record(stamp):
    """One valid session record with a chosen timestamp."""
    return {
        "subject": "AMANDA", "session": "day1", "recorded_at": stamp,
        "features": {
            "duration_s": 6.0, "f0_mean_hz": 120.0, "f0_sd_hz": 2.0,
            "intensity_db": 85.0, "jitter_local": 0.01, "shimmer_local": 0.02,
            "hnr_db": 20.0, "pause_ratio": 0.1, "voiced_rate_hz": 60.0,
        },
    }


def published(tmp_path, stamp, with_times=False):
    sessions = tmp_path / "sessions.jsonl"
    context = tmp_path / "context.jsonl"
    sessions.write_text(json.dumps(record(stamp)) + "\n", encoding="utf-8")
    context.write_text("", encoding="utf-8")
    return build(sessions, context, "AMANDA", "A. R.", False, with_times)


def test_public_stamp_drops_the_clock_time():
    """A stored ISO timestamp becomes its date; other values pass through."""
    assert public_stamp("2026-11-15T15:23:25-05:00") == "2026-11-15"
    assert public_stamp("2026-11-15") == "2026-11-15"
    assert public_stamp(None) is None


def test_published_report_has_dates_only_by_default(tmp_path):
    """The builder strips the time and the timezone without being asked."""
    report = published(tmp_path, "2026-11-15T15:23:25-05:00")
    assert report["recorded_at"] == ["2026-11-15"]
    assert report["display_name"] == "A. R."


def test_times_are_kept_only_when_explicitly_requested(tmp_path):
    """--with-times remains available for a private or consented copy."""
    report = published(tmp_path, "2026-11-15T15:23:25-05:00", with_times=True)
    assert report["recorded_at"] == ["2026-11-15T15:23:25-05:00"]


def test_committed_real_report_has_no_clock_times():
    """Both published copies of the real dataset carry dates, not times."""
    for name in ("web/app/real_report.json", "docs/example/real_report.json"):
        data = json.loads((ROOT / name).read_text(encoding="utf-8"))
        assert all("T" not in (value or "") for value in data.get("recorded_at", [])), name
