"""
Turn structured check-in answers into the explains map.

The rules mirror pipeline/checkin_agent.py: a true yes/no or a short sleep can
account for specific features; non-upright posture licenses pitch and pausing;
headache licenses nothing because it has no established acoustic signature.
Keeping the copy here lets the web app share the CLI's field definitions while
staying import-safe for tests.
"""
import re

from pipeline.checkin_agent import QUESTIONS

POSTURE_RE = re.compile(r"reclin|lying|lie|supine|lay|float|weightless", re.I)
POSTURE_FEATURES = ["f0_mean_hz", "f0_sd_hz", "intensity_db", "hnr_db", "pause_ratio"]


def build_explains(answers: dict) -> dict:
    """Return feature -> [reported reasons] for movements that are accounted for."""
    explains: dict[str, list[str]] = {}
    for question in QUESTIONS:
        field = question["field"]
        value = answers.get(field)
        triggered = value is True or (
            question["type"] == "number"
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and value < 6
        )
        licensed = list(question["explains"])
        if field == "posture" and isinstance(value, str) and POSTURE_RE.search(value):
            triggered = True
            licensed = POSTURE_FEATURES
        if triggered and licensed:
            for feature in licensed:
                explains.setdefault(feature, []).append(field)
    return explains
