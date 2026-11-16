"""
Build the report JSON the one-page UI renders.

Findings come from the same analyse() the CLI uses, so the UI cannot drift from
the validated gate logic. Only presentation is added here: labels, units,
series, and the explained-versus-unexplained ordering.
"""
import statistics
from collections import defaultdict

from pipeline.voice_drift import MIN_CHANGE, analyse

LABEL = {
    "f0_mean_hz": "Pitch", "f0_sd_hz": "Pitch variation",
    "intensity_db": "Loudness", "jitter_local": "Pitch steadiness",
    "shimmer_local": "Loudness steadiness", "hnr_db": "Voice clarity",
    "pause_ratio": "Pausing", "voiced_rate_hz": "Speaking rate",
}
UNITS = {
    "f0_mean_hz": " Hz", "f0_sd_hz": " Hz", "intensity_db": " dB",
    "jitter_local": "", "shimmer_local": "", "hnr_db": " dB",
    "pause_ratio": "", "voiced_rate_hz": "/s",
}


HINT = {
    "f0_mean_hz": "How high or low your voice is.",
    "f0_sd_hz": "How much your pitch moves as you speak.",
    "intensity_db": "How loud your voice is.",
    "jitter_local": "Tiny wobble in pitch from one cycle to the next. Lower is steadier.",
    "shimmer_local": "Tiny wobble in loudness from one cycle to the next. Lower is steadier.",
    "hnr_db": "How clear the voice is against breath and noise. Higher is clearer.",
    "pause_ratio": "Share of the reading spent silent.",
    "voiced_rate_hz": "How much voiced sound per second. Higher is faster.",
}


def _fmt(feature, value):
    """One readable number per measure; raw values stay in the JSON beside it."""
    if value is None:
        return "not measured"
    if feature in ("jitter_local", "shimmer_local", "pause_ratio"):
        return f"{value * 100:.2f}%" if feature != "pause_ratio" else f"{value * 100:.1f}%"
    if feature == "voiced_rate_hz":
        return f"{value:.1f} per second"
    return f"{value:.1f}{UNITS.get(feature, '')}"


def _fmt_spread(feature, sd):
    if feature in ("jitter_local", "shimmer_local", "pause_ratio"):
        return f"{sd * 100:.2f} points"
    if feature == "voiced_rate_hz":
        return f"{sd:.1f}"
    return f"{sd:.1f}{UNITS.get(feature, '')}"


def _measures(records, n_baseline, flagged):
    """Every measure with its numbers, so a quiet report still shows the data."""
    baseline = records[:n_baseline]
    rows = []
    for feature in MIN_CHANGE:
        series = [r["features"].get(feature) for r in records]
        latest = next((v for v in reversed(series) if v is not None), None)
        base_vals = [v for v in (r["features"].get(feature) for r in baseline)
                     if v is not None]
        mean = statistics.mean(base_vals) if base_vals else None
        sd = statistics.stdev(base_vals) if len(base_vals) >= 2 else None
        complete = len(records) >= n_baseline
        if latest is None or mean is None:
            change = ""
        else:
            delta = latest - mean
            direction = "above" if delta > 0 else "below"
            amount = _fmt_spread(feature, abs(delta))
            # A difference that rounds to zero reads as "same", not "0.0 below".
            shown = float("".join(c for c in amount.split()[0] if c.isdigit() or c == "."))
            change = ("same as your baseline" if shown == 0 else
                      f"{amount} {direction} your baseline")
        rows.append({
            "feature": feature,
            "label": LABEL.get(feature, feature),
            "hint": HINT.get(feature, ""),
            "format": ("percent2" if feature in ("jitter_local", "shimmer_local")
                       else "percent1" if feature == "pause_ratio"
                       else "rate" if feature == "voiced_rate_hz"
                       else "hz" if feature.endswith("_hz") else "db"),
            "series": series,
            "latest": latest,
            "baseline_mean": mean,
            "baseline_sd": sd,
            "baseline_complete": complete,
            "latest_text": _fmt(feature, latest),
            "baseline_text": _fmt(feature, mean) if mean is not None else "",
            "spread_text": _fmt_spread(feature, sd) if sd is not None else "",
            "change_text": change,
            "flagged": feature in flagged,
        })
    return rows


def _findings_for(stats, findings, subject, records, context):
    by_feature = defaultdict(list)
    for finding in findings:
        by_feature[finding["feature"]].append(finding)
    session_names = [r["session"] for r in records]

    rows = []
    for feature, items in by_feature.items():
        latest = items[-1]
        reasons = context.get((subject, latest["session"]), {}).get(feature, [])
        flagged = [session_names.index(item["session"]) for item in items]
        rows.append({
            "feature": feature,
            "label": LABEL.get(feature, feature),
            "phrase": latest["phrase"],
            "value": latest["value"],
            "unit": UNITS.get(feature, ""),
            "baseline_mean": latest["baseline_mean"],
            "baseline_sd": round(stats[feature]["sd"], 4),
            "z": latest["z"],
            "delta": latest["delta"],
            "run_length": latest.get("run_length", len(items)),
            "explained": reasons,
            "explained_by": reasons,
            "series": [r["features"].get(feature) for r in records],
            "flagged_indices": flagged,
            "value_text": _fmt(feature, latest["value"]),
            "baseline_text": _fmt(feature, latest["baseline_mean"]),
            "spread_text": _fmt_spread(feature, stats[feature]["sd"]),
        })
    return sorted(rows, key=lambda row: (bool(row["explained"]), row["feature"]))


def build_report(records, context, subject, n_baseline=3, z_threshold=2.0, min_run=2,
                 baseline_start=None):
    """Return the report state for one subject. Records stay in append order.

    baseline_start names the session the baseline begins at. Sessions before it
    are kept and listed, but are not part of the baseline and are not scored.
    That is how a crew member re-sets their baseline, for example once their
    voice has settled after the first week in orbit.
    """
    every = [r for r in records if r.get("subject") == subject]
    start = 0
    if baseline_start is not None:
        names = [r.get("session") for r in every]
        if baseline_start in names:
            start = names.index(baseline_start)
    earlier, subject_records = every[:start], every[start:]

    base = {
        "subject": subject,
        "state": "empty",
        "session_count": len(subject_records),
        "n_baseline": n_baseline,
        "baseline_progress": {"have": min(len(subject_records), n_baseline),
                              "need": n_baseline},
        "headline": "No sessions yet",
        "findings": [],
        "stable_features": [],
        "measures": [],
        "total_sessions": len(every),
        "baseline_moved": start > 0,
        "baseline_start": subject_records[0]["session"] if subject_records else None,
        "earlier": [{"session": r["session"], "recorded_at": r.get("recorded_at")}
                    for r in earlier],
    }
    if not subject_records:
        return base
    base["sessions"] = [r["session"] for r in subject_records]
    base["recorded_at"] = [r.get("recorded_at") for r in subject_records]
    base["measures"] = _measures(subject_records, n_baseline, set())
    if len(subject_records) <= n_baseline:
        # The first n_baseline sessions define the reference distribution, so
        # the session that completes it cannot also be scored against itself.
        # Reporting "stable" here would claim movement was checked when no
        # later session exists yet.
        base["state"] = "baseline"
        if len(subject_records) == n_baseline:
            base["headline"] = ("Baseline complete: scoring begins with your "
                                "next session.")
        else:
            base["headline"] = (f"Building your baseline: {len(subject_records)} "
                                f"of {n_baseline} sessions")
        return base

    stats, findings = analyse(subject_records, n_baseline, z_threshold, min_run)
    rows = _findings_for(stats, findings, subject, subject_records, context)
    by_feature = {row["feature"] for row in rows}
    base["stable_features"] = [
        {"feature": feature, "label": LABEL.get(feature, feature)}
        for feature in MIN_CHANGE if feature in stats and feature not in by_feature
    ]
    base["findings"] = rows
    base["measures"] = _measures(subject_records, n_baseline, by_feature)

    if not findings:
        base["state"] = "stable"
        base["headline"] = "Nothing moved far enough from your baseline to report"
        return base

    unexplained = sum(1 for row in rows if not row["explained"])
    base["state"] = "findings"
    if unexplained:
        base["headline"] = (f"{unexplained} change{'s' if unexplained != 1 else ''} "
                            f"without a reported explanation")
    else:
        base["headline"] = "Everything that moved has a reported explanation"
    return base


def session_detail(record, answers, questions):
    """One session for the Your sessions list: its numbers and check-in answers.

    answers is the stored check-in (parsed values plus the words used), or None
    when no check-in was saved with the session.
    """
    features = record.get("features", {})
    measures = [{"feature": f, "label": LABEL.get(f, f),
                 "value_text": _fmt(f, features.get(f))} for f in MIN_CHANGE]
    checkin = None
    if answers is not None:
        checkin = [{"field": q["field"], "ask": q["ask"],
                    "answer": answers.get(q["field"] + "_raw") or "Not answered"}
                   for q in questions]
    return {"subject": record.get("subject"), "session": record.get("session"),
            "recorded_at": record.get("recorded_at"),
            "measures": measures, "checkin": checkin}
