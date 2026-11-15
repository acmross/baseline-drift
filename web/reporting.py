"""
Build the report JSON the one-page UI renders.

Findings come from the same analyse() the CLI uses, so the UI cannot drift from
the validated gate logic. Only presentation is added here: labels, units,
series, and the explained-versus-unexplained ordering.
"""
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
        })
    return sorted(rows, key=lambda row: (bool(row["explained"]), row["feature"]))


def build_report(records, context, subject, n_baseline=3, z_threshold=2.0, min_run=2):
    """Return the report state for one subject. Records stay in append order."""
    subject_records = [r for r in records if r.get("subject") == subject]

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
    }
    if not subject_records:
        return base
    if len(subject_records) <= n_baseline:
        # The first n_baseline sessions define the reference distribution, so
        # the session that completes it cannot also be scored against itself.
        # Reporting "stable" here would claim movement was checked when no
        # later session exists yet.
        base["state"] = "baseline"
        if len(subject_records) == n_baseline:
            base["headline"] = ("Baseline complete — scoring begins with your "
                                "next session.")
        else:
            base["headline"] = (f"Building your baseline — {len(subject_records)} "
                                f"of {n_baseline} sessions")
        return base

    stats, findings = analyse(subject_records, n_baseline, z_threshold, min_run)
    # pipeline.voice_drift.analyse has an operator-precedence bug on its empty
    # return: it yields (stats, (stats, [])) instead of (stats, []). The
    # pipeline is read-only here, so normalise the shape before presentation.
    if isinstance(findings, tuple):
        findings = findings[1]
    rows = _findings_for(stats, findings, subject, subject_records, context)
    by_feature = {row["feature"] for row in rows}
    base["stable_features"] = [
        {"feature": feature, "label": LABEL.get(feature, feature)}
        for feature in MIN_CHANGE if feature in stats and feature not in by_feature
    ]
    base["findings"] = rows

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
