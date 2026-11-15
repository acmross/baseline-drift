"""
Baseline Drift: baseline-deviation detector for voice check-ins.

Same two-gate logic validated on NASA OSD-575 (see drift3.py). Gate 1 is a
z-score against the speaker's OWN baseline sessions. Gate 2 replaces the
clinical reference range, which voice does not have, with a minimum
meaningful change in the feature's natural units.

Why two gates: on OSD-575, a z-score alone flagged 65 of 272 comparisons,
about a quarter, because a three-sample baseline gives a tiny unstable
standard deviation. Adding a second gate cut that to 11. A three-session
voice baseline has exactly the same problem.

Output is descriptive by design. It reports what moved and by how much.
It never names a cause.

Usage:
    python3 voice_drift.py sessions.jsonl [--baseline 3] [--z 2.0]
"""
import sys, json, argparse, os, statistics as st
from collections import defaultdict

# Gate 2 thresholds: the smallest change in each feature we are willing to
# call real. PLACEHOLDERS. Calibrate from your own repeated baseline
# recordings: record the same passage several times in one sitting, measure
# the spread, and set each threshold above that session-to-session noise.
# Too low and you reproduce the OSD-575 false-positive problem; too high and
# you detect nothing.
MIN_CHANGE = {
    "f0_mean_hz":     5.0,    # Hz
    "f0_sd_hz":       5.0,    # Hz
    "intensity_db":   2.0,    # dB
    "jitter_local":   0.004,  # ratio
    "shimmer_local":  0.02,   # ratio
    "hnr_db":         1.5,    # dB
    "pause_ratio":    0.05,   # share of frames
    "voiced_rate_hz": 5.0,    # voiced frames per second
}

# Plain-language direction labels. Descriptive only: no cause, no diagnosis.
DIRECTION = {
    "f0_mean_hz":     ("pitch is higher",          "pitch is lower"),
    "f0_sd_hz":       ("pitch varies more",        "pitch varies less"),
    "intensity_db":   ("voice is louder",          "voice is quieter"),
    "jitter_local":   ("pitch is less steady",     "pitch is steadier"),
    "shimmer_local":  ("loudness is less steady",  "loudness is steadier"),
    "hnr_db":         ("voice is clearer",         "voice is breathier or noisier"),
    "pause_ratio":    ("more pausing",             "less pausing"),
    "voiced_rate_hz": ("speaking faster",          "speaking slower"),
}


def load_context(path):
    """
    Session context from checkin_agent.py: what the speaker reported.
    Maps (subject, session) -> {feature: [reasons]} for features whose
    movement already has a mundane explanation.
    """
    ctx = {}
    if not path or not os.path.exists(path):
        return ctx
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line: continue
            rec = json.loads(line)
            ctx[(rec["subject"], rec["session"])] = rec.get("explains", {})
    return ctx


def load(path):
    by_subject = defaultdict(list)
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rec = json.loads(line)
                by_subject[rec["subject"]].append(rec)
    return by_subject


def consecutive_runs(findings, sessions_order, min_run):
    """
    Gate 3: keep a finding only if the same feature moved the same direction
    on at least `min_run` CONSECUTIVE sessions.

    Why this exists: on synthetic control data where nothing changed, gates 1
    and 2 still fired on a single isolated session. One session is noise, a
    run is a signal. This is the voice equivalent of not acting on one odd
    lab value.
    """
    pos = {s: i for i, s in enumerate(sessions_order)}
    by_feat = defaultdict(list)
    for f in findings:
        by_feat[(f["feature"], f["delta"] > 0)].append(f)

    kept = []
    for _, group in by_feat.items():
        group.sort(key=lambda f: pos[f["session"]])
        run = [group[0]]
        for prev, cur in zip(group, group[1:]):
            if pos[cur["session"]] == pos[prev["session"]] + 1:
                run.append(cur)
            else:
                if len(run) >= min_run: kept.extend(run)
                run = [cur]
        if len(run) >= min_run: kept.extend(run)
    for f in kept:
        f["run_length"] = sum(1 for k in kept
                              if k["feature"] == f["feature"]
                              and (k["delta"] > 0) == (f["delta"] > 0))
    return kept


def analyse(records, n_baseline, z_threshold, min_run=2):
    """Returns (baseline_stats, [findings]) for one speaker."""
    baseline, later = records[:n_baseline], records[n_baseline:]
    if len(baseline) < n_baseline:
        return None, []

    stats = {}
    for feat in MIN_CHANGE:
        vals = [r["features"].get(feat) for r in baseline]
        vals = [v for v in vals if v is not None]
        if len(vals) < 2:
            continue
        sd = st.stdev(vals)
        stats[feat] = {"mean": st.mean(vals), "sd": sd, "n": len(vals)}

    findings = []
    for rec in later:
        for feat, s in stats.items():
            v = rec["features"].get(feat)
            if v is None or s["sd"] == 0:
                continue
            z = (v - s["mean"]) / s["sd"]
            delta = v - s["mean"]
            gate1 = abs(z) >= z_threshold
            gate2 = abs(delta) >= MIN_CHANGE[feat]
            if gate1 and gate2:
                up, down = DIRECTION[feat]
                findings.append({
                    "session": rec["session"], "feature": feat,
                    "z": round(z, 1), "value": round(v, 4),
                    "baseline_mean": round(s["mean"], 4), "delta": round(delta, 4),
                    "phrase": up if delta > 0 else down,
                })
    order = [r["session"] for r in later]
    return stats, consecutive_runs(findings, order, min_run) if findings else (stats, [])


def report(subject, stats, findings, n_baseline, context=None):
    print(f"\n=== {subject} ===")
    if stats is None:
        print(f"  Not enough baseline sessions (need {n_baseline}).")
        return
    print(f"  Baseline from {stats[list(stats)[0]]['n']} sessions.")
    if not findings:
        print("  No feature moved far enough from baseline to report.")
        return

    by_session = defaultdict(list)
    for f in findings:
        by_session[f["session"]].append(f)

    # A single session's drift is weaker evidence than the same feature moving
    # several sessions running. Count runs so the report can say so.
    runs = {f["feature"]: f.get("run_length", 1) for f in findings}

    context = context or {}
    for session, items in by_session.items():
        explained = context.get((subject, session), {})
        print(f"\n  {session}")
        for f in items:
            n = runs[f["feature"]]
            streak = f" ({n} sessions showing this)" if n > 1 else ""
            reasons = explained.get(f["feature"])
            tag = "  [reported: " + ", ".join(reasons) + "]" if reasons else ""
            print(f"    {f['phrase']}{streak}{tag}")
            print(f"      {f['feature']}: {f['value']} vs baseline {f['baseline_mean']} "
                  f"(z={f['z']:+}, change {f['delta']:+})")
        unexplained = [f for f in items if not explained.get(f["feature"])]
        if explained and not unexplained:
            print("    Everything that moved this session has a reported explanation.")
        elif explained and unexplained:
            print(f"    {len(unexplained)} of {len(items)} changes have no reported explanation.")
    print("\n  These are measurements relative to this speaker's own baseline.")
    print("  They describe what changed, not why. Causes include ordinary ones:")
    print("  a head cold, a different microphone, time of day, or the room.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sessions")
    ap.add_argument("--baseline", type=int, default=3)
    ap.add_argument("--z", type=float, default=2.0)
    ap.add_argument("--persist", type=int, default=2,
                    help="consecutive sessions a feature must move before reporting")
    ap.add_argument("--context", default="context.jsonl",
                    help="session context from checkin_agent.py")
    args = ap.parse_args()

    context = load_context(args.context)
    for subject, records in load(args.sessions).items():
        stats, findings = analyse(records, args.baseline, args.z, args.persist)
        report(subject, stats, findings, args.baseline, context)


if __name__ == "__main__":
    main()
