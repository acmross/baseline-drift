"""
Build a report from real saved sessions, for the online preview.

Reads a sessions.jsonl and context.jsonl copied from a machine that ran the
app, runs them through the same build_report() the app uses, and writes
web/app/real_report.json. Measurements and dates are always included. Check-in
answers are left out unless --with-checkin is given, because they are the
crew member's own and publishing them is their decision. Audio is never copied.

Usage:
    python web/make_real_report.py SESSIONS.jsonl CONTEXT.jsonl \
        --subject AMANDA --name "Amanda Ross" [--with-checkin]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.checkin_agent import QUESTIONS             # noqa: E402
from web.reporting import build_report, session_detail   # noqa: E402
from web.session_store import read_records               # noqa: E402


def build(sessions_path, context_path, subject, name, with_checkin):
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
    if not with_checkin:
        report["checkin_note"] = "Check-in answers are not published in this preview."
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sessions")
    parser.add_argument("context")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--with-checkin", action="store_true")
    args = parser.parse_args()
    report = build(args.sessions, args.context, args.subject, args.name, args.with_checkin)
    target = ROOT / "web" / "app" / "real_report.json"
    target.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {target.relative_to(ROOT)}: {report['session_count']} sessions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
