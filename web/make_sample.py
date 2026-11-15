"""
Build the sample report the app can show in place of a real crew member.

The readings are invented: a simulated crew member checked in every other day
for ten weeks, stayed steady, then paused more and spoke more slowly over the
last four sessions while also reporting a cold. The numbers go through the
same build_report() the real app uses, so the sample shows the real report and
trend views, with made-up data. Nothing here comes from a real voice.

Usage:
    python web/make_sample.py            # rewrites web/app/sample_report.json
"""
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web.context_builder import build_explains          # noqa: E402
from pipeline.checkin_agent import QUESTIONS             # noqa: E402
from web.reporting import build_report, session_detail   # noqa: E402

SUBJECT = "SAMPLE"
SESSIONS = 36
BASE = {"f0_mean_hz": 198.0, "f0_sd_hz": 32.0, "intensity_db": 68.0,
        "jitter_local": 0.011, "shimmer_local": 0.055, "hnr_db": 17.0,
        "pause_ratio": 0.14, "voiced_rate_hz": 52.0}
NOISE = {"f0_mean_hz": 2.5, "f0_sd_hz": 2.0, "intensity_db": 0.8,
         "jitter_local": 0.0010, "shimmer_local": 0.004, "hnr_db": 0.5,
         "pause_ratio": 0.010, "voiced_rate_hz": 1.2}
# The last four sessions: slower and more halting, plus the lower, breathier,
# quieter voice a cold produces.
LATE = {"pause_ratio": 0.085, "voiced_rate_hz": -9.0, "f0_mean_hz": -14.0,
        "hnr_db": -3.2, "intensity_db": -4.5}


def build():
    rng = random.Random(11)
    start = datetime(2026, 9, 1, 9, 15, tzinfo=timezone(timedelta(hours=-5)))
    records, context, details = [], {}, {}
    for index in range(SESSIONS):
        features = {name: value + rng.gauss(0, NOISE[name]) for name, value in BASE.items()}
        late = index >= SESSIONS - 4
        if late:
            for name, shift in LATE.items():
                features[name] += shift
        session = f"fd{index + 1}"
        records.append({
            "subject": SUBJECT, "session": session,
            "recorded_at": (start + timedelta(days=2 * index,
                                              minutes=rng.randint(0, 240))
                            ).isoformat(timespec="seconds"),
            "features": {**{k: round(v, 5) for k, v in features.items()},
                         "duration_s": round(21.5 + rng.gauss(0, 0.6), 2)},
        })
        answers = {"cold_or_congestion": late, "cough": False, "sleep_hours": 7.5,
                   "unusual_pain": "no", "posture": "sitting", "setup_changed": False}
        context[(SUBJECT, session)] = build_explains(answers)
        said = {"cold_or_congestion_raw": "yes: a cold" if late else "no",
                "cough_raw": "no", "sleep_hours_raw": "7.5", "unusual_pain_raw": "no",
                "posture_raw": "sitting", "setup_changed_raw": "yes"}
        details[session] = session_detail(records[-1], said, QUESTIONS)
        details[session]["takes"] = []
    report = build_report(records, context, SUBJECT)
    report["sample"] = True
    report["details"] = details
    report["audio_note"] = "Sample data has no audio."
    return report


def main() -> int:
    target = ROOT / "web" / "app" / "sample_report.json"
    target.write_text(json.dumps(build(), indent=1) + "\n", encoding="utf-8")
    print(f"wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
