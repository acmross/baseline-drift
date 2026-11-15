"""Append-only JSONL storage and identifier validation."""
import pytest

from web.session_store import validate_id, append_record, read_records, has_session


def test_validate_id_accepts_normal_values():
    assert validate_id("AMANDA", "subject") == "AMANDA"
    assert validate_id("CDR-01", "subject") == "CDR-01"
    assert validate_id("day-12", "session") == "day-12"


@pytest.mark.parametrize("value", ["../etc", "", "AMANDA", "A" * 40, "day 1"])
def test_validate_id_rejects_bad_values(value):
    with pytest.raises(ValueError):
        validate_id(value, "session")


def test_append_and_read_roundtrip(tmp_path):
    path = tmp_path / "sessions.jsonl"
    append_record(path, {"subject": "AMANDA", "session": "day1"})
    append_record(path, {"subject": "AMANDA", "session": "day2"})
    assert [r["session"] for r in read_records(path)] == ["day1", "day2"]


def test_read_missing_file_returns_empty(tmp_path):
    assert read_records(tmp_path / "missing.jsonl") == []


def test_has_session():
    records = [{"subject": "AMANDA", "session": "day1"}]
    assert has_session(records, "AMANDA", "day1") is True
    assert has_session(records, "AMANDA", "day2") is False
