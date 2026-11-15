"""
Append-only JSONL storage for Baseline Drift sessions and check-in context.

Identifiers are validated before they touch the filesystem because the subject
and session names become path segments under web/data/recordings/.
"""
import json
import re
from pathlib import Path

SUBJECT_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,15}$")
SESSION_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,15}$")


def validate_id(value: str, kind: str) -> str:
    """Return a safe subject or session identifier, or raise ValueError."""
    pattern = SUBJECT_RE if kind == "subject" else SESSION_RE
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"invalid {kind}: {value!r}")
    return value


def append_record(path: Path, record: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_records(path: Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    records = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def remove_session(path: Path, subject: str, session: str) -> int:
    """Rewrite a JSONL file without one subject/session; return how many were dropped."""
    path = Path(path)
    if not path.exists():
        return 0
    records = read_records(path)
    kept = [r for r in records
            if not (r.get("subject") == subject and r.get("session") == session)]
    if len(kept) != len(records):
        with path.open("w", encoding="utf-8") as fh:
            for record in kept:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return len(records) - len(kept)


def has_session(records: list[dict], subject: str, session: str) -> bool:
    return any(r.get("subject") == subject and r.get("session") == session for r in records)
