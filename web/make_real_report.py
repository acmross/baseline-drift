"""
Build a report from real saved sessions, for the online preview.

Reads a sessions.jsonl and context.jsonl copied from a machine that ran the
app, runs them through the same build_report() the app uses, and writes
web/app/real_report.json. Measurements and dates are included; clock times are
not, unless --with-times is given, because a published report only needs the
day. Use initials or the subject code for --name, never a full name. Check-in
answers are left out unless --with-checkin is given, because they are the
crew member's own and publishing them is their decision. Audio is never copied.

Usage:
    python web/make_real_report.py SESSIONS.jsonl CONTEXT.jsonl \
        --subject AMANDA --name "A. R." [--with-checkin] [--with-times]
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.checkin_agent import QUESTIONS             # noqa: E402
from web.reporting import build_report, session_detail   # noqa: E402
from web.session_store import read_records               # noqa: E402


def public_stamp(value):
    """Turn one stored timestamp into the public form: the date, no clock time."""
    if not isinstance(value, str):
        return value
    match = re.match(r"^(\d{4}-\d{2}-\d{2})T", value)
    return match.group(1) if match else value


def build(sessions_path, context_path, subject, name, with_checkin, with_times=False):
    records = [r for r in read_records(Path(sessions_path)) if r.get("subject") == subject]
    entries = [r for r in read_records(Path(context_path)) if r.get("subject") == subject]
    context = {(r["subject"], r["session"]): r.get("explains", {}) for r in entries}
    answers = {r["session"]: r.get("answers", {}) for r in entries}
    report = build_report(records, context, subject)
    report["sample"] = True            # shown through the same read-only path
    report["real"] = True
    report["display_name"] = name
    report["details"] = {}
    for record in records:
        detail = session_detail(
            record, answers.get(record["session"]) if with_checkin else None, QUESTIONS)
        detail["takes"] = []
        report["details"][record["session"]] = detail
    report["audio_note"] = "Recordings are not published in this preview."
    if not with_times:
        # The published report needs the day, not the clock time. Dropping the
        # time also drops the timezone the laptop recorded it in.
        report["recorded_at"] = [public_stamp(v) for v in report.get("recorded_at", [])]
        for detail in report.get("details", {}).values():
            detail["recorded_at"] = public_stamp(detail.get("recorded_at"))
    if not with_checkin:
        report["checkin_note"] = "Check-in answers are not published in this preview."
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sessions")
    parser.add_argument("context")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--name", required=True,
                        help="initials or a subject code, never a full name")
    parser.add_argument("--with-checkin", action="store_true")
    parser.add_argument("--with-times", action="store_true",
                        help="publish clock times too (default: dates only)")
    args = parser.parse_args()
    report = build(args.sessions, args.context, args.subject, args.name,
                   args.with_checkin, args.with_times)
    target = ROOT / "web" / "app" / "real_report.json"
    target.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {target.relative_to(ROOT)}: {report['session_count']} sessions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
