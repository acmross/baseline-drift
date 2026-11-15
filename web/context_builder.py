"""
Turn check-in answers into the explains map the report uses.

Two entry points, both mirroring pipeline/checkin_agent.py:

  build_answers_from_raw  parses the UI's raw answer strings with the same
                          parse_plain rules as the CLI and keeps the raw text
                          beside each parsed value.
  build_explains          applies the same licensing rules as the CLI so a
                          reported cold, cough, short sleep, setup change, or
                          non-upright posture accounts for the same features.

Keeping this here lets the web app share the CLI's field definitions while
staying import-safe for tests.
"""
import re

from pipeline.checkin_agent import QUESTIONS, parse_plain

POSTURE_RE = re.compile(r"reclin|lying|lie|supine|lay|float|weightless", re.I)
POSTURE_FEATURES = ["f0_mean_hz", "f0_sd_hz", "intensity_db", "hnr_db", "pause_ratio"]


def build_answers_from_raw(raw: dict) -> dict:
    """Parse the UI's raw answers exactly like checkin_agent.main.

    Returns one parsed ``field`` and one ``field_raw`` entry per question.
    Unknown keys are ignored because QUESTIONS owns the vocabulary. A non-
    string, non-null value raises ValueError so the endpoint can answer 422
    instead of silently coercing a malformed client payload.
    """
    if not isinstance(raw, dict):
        raise ValueError("raw must be an object")
    answers: dict = {}
    for question in QUESTIONS:
        field = question["field"]
        text = raw.get(field)
        if text is not None and not isinstance(text, str):
            raise ValueError(f"raw.{field} must be a string or null")
        answers[field] = parse_plain(text, question["type"])
        answers[field + "_raw"] = (text or "").strip() or None
    return answers


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
