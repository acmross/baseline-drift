"""
Baseline Drift: renders the crew-facing report as one self-contained HTML file.

No server, no network, no external assets. Open it with a browser on the
habitat machine. This is the screen the crew member reads.

Usage:
    python3 make_report.py sessions.jsonl --context context.jsonl --out report.html
"""
import sys, json, argparse, os, statistics as st
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from voice_drift import load, load_context, analyse, MIN_CHANGE, DIRECTION

UNITS = {
    "f0_mean_hz": "Hz", "f0_sd_hz": "Hz", "intensity_db": "dB",
    "jitter_local": "", "shimmer_local": "", "hnr_db": "dB",
    "pause_ratio": "", "voiced_rate_hz": "/s",
}
LABEL = {
    "f0_mean_hz": "Pitch", "f0_sd_hz": "Pitch variation",
    "intensity_db": "Loudness", "jitter_local": "Pitch steadiness",
    "shimmer_local": "Loudness steadiness", "hnr_db": "Voice clarity",
    "pause_ratio": "Pausing", "voiced_rate_hz": "Speaking rate",
}


def sparkline(values, mean, sd, flagged_idx, w=220, h=44, pad=6):
    """One series, baseline band behind it. No legend needed for a single series."""
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return ""
    lo = min(min(vals), mean - 2.5 * sd)
    hi = max(max(vals), mean + 2.5 * sd)
    if hi == lo:
        hi = lo + 1

    def x(i): return pad + i * (w - 2 * pad) / max(len(values) - 1, 1)
    def y(v): return h - pad - (v - lo) * (h - 2 * pad) / (hi - lo)

    band_top, band_bot = y(mean + sd), y(mean - sd)
    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(values) if v is not None)
    dots = "".join(
        f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="{4 if i in flagged_idx else 2.5}" '
        f'class="{"dot flag" if i in flagged_idx else "dot"}"/>'
        for i, v in enumerate(values) if v is not None)
    return f'''<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img"
  aria-label="trend across sessions, baseline band shaded">
  <rect x="0" y="{band_top:.1f}" width="{w}" height="{max(band_bot-band_top,1):.1f}" class="band"/>
  <line x1="0" y1="{y(mean):.1f}" x2="{w}" y2="{y(mean):.1f}" class="meanline"/>
  <polyline points="{pts}" class="series"/>{dots}
</svg>'''


def build(subject, records, stats, findings, context, n_baseline):
    sessions = [r["session"] for r in records]
    later = sessions[n_baseline:]
    by_feat = defaultdict(list)
    for f in findings:
        by_feat[f["feature"]].append(f)

    explained_count = unexplained_count = 0
    rows = []
    for feat in MIN_CHANGE:
        if feat not in stats or feat not in by_feat:
            continue
        s = stats[feat]
        series = [r["features"].get(feat) for r in records]
        flagged = {sessions.index(f["session"]) for f in by_feat[feat]}
        latest = by_feat[feat][-1]
        reasons = context.get((subject, latest["session"]), {}).get(feat)
        if reasons: explained_count += 1
        else: unexplained_count += 1
        run = len(by_feat[feat])
        tag = (f'<span class="tag explained">accounted for: {", ".join(r.replace("_"," ") for r in reasons)}</span>'
               if reasons else '<span class="tag open">no reported explanation</span>')
        rows.append(f'''
      <div class="row{'' if reasons else ' open-row'}">
        <div class="meta">
          <div class="label">{LABEL[feat]}</div>
          <div class="phrase">{latest["phrase"]}</div>
          <div class="detail">{latest["value"]}{UNITS[feat]} against your baseline of
            {round(s["mean"],2)}{UNITS[feat]} &middot; {run} session{"s" if run>1 else ""} running</div>
          {tag}
        </div>
        <div class="spark">{sparkline(series, s["mean"], s["sd"], flagged)}</div>
      </div>''')

    if not rows:
        body = '<div class="none">Nothing has moved far enough from your baseline to report.</div>'
        headline = "No changes to review"
    else:
        body = "".join(rows)
        headline = (f"{unexplained_count} change{'s' if unexplained_count!=1 else ''} "
                    f"without a reported explanation") if unexplained_count else \
                   "Everything that moved has a reported explanation"

    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Voice check-in &middot; {subject}</title>
<style>
  :root {{
    --surface-0:#121211; --surface-1:#1a1a19; --surface-2:#232322;
    --text-primary:#f0efec; --text-secondary:#c3c2b7; --text-muted:#8a897f;
    --series-1:#3987e5; --accent:#d95926; --line:#32322f;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--surface-0); color:var(--text-primary);
    font:15px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; }}
  .wrap {{ max-width:760px; margin:0 auto; padding:40px 24px 64px; }}
  header {{ border-bottom:1px solid var(--line); padding-bottom:20px; margin-bottom:28px; }}
  h1 {{ font-size:19px; margin:0 0 4px; font-weight:600; letter-spacing:-0.01em; }}
  .sub {{ color:var(--text-muted); font-size:13px; }}
  .headline {{ font-size:17px; margin:22px 0 6px; font-weight:600; }}
  .headline.clear {{ color:var(--text-secondary); font-weight:500; }}
  .baseline-note {{ color:var(--text-muted); font-size:13px; margin-bottom:26px; }}
  .row {{ display:flex; gap:20px; align-items:center; justify-content:space-between;
    padding:16px 0 16px 14px; border-top:1px solid var(--line);
    border-left:2px solid transparent; }}
  .row.open-row {{ border-left-color:var(--accent); }}
  .label {{ font-size:12px; text-transform:uppercase; letter-spacing:.07em;
    color:var(--text-muted); margin-bottom:3px; }}
  .phrase {{ font-size:16px; font-weight:600; margin-bottom:3px; }}
  .detail {{ color:var(--text-secondary); font-size:13px; }}
  .tag {{ display:inline-block; margin-top:8px; font-size:12px; padding:2px 8px;
    border-radius:3px; border:1px solid var(--line); background:var(--surface-2); }}
  .tag.explained {{ color:var(--text-muted); }}
  .tag.open {{ color:var(--text-primary); border-color:var(--accent); }}
  .tag.open::before {{ content:"\\25B2  "; color:var(--accent); font-size:10px; }}
  .tag.explained::before {{ content:"\\2713  "; color:var(--text-muted); }}
  .spark {{ flex:0 0 auto; }}
  .band {{ fill:var(--surface-2); }}
  .meanline {{ stroke:var(--text-muted); stroke-width:1; stroke-dasharray:3 3; opacity:.6; }}
  .series {{ fill:none; stroke:var(--series-1); stroke-width:2;
    stroke-linejoin:round; stroke-linecap:round; }}
  .dot {{ fill:var(--series-1); stroke:var(--surface-0); stroke-width:2; }}
  .dot.flag {{ fill:var(--accent); }}
  .none {{ color:var(--text-secondary); padding:28px 0; border-top:1px solid var(--line); }}
  footer {{ margin-top:34px; padding-top:20px; border-top:1px solid var(--line);
    color:var(--text-muted); font-size:13px; }}
  footer strong {{ color:var(--text-secondary); font-weight:600; }}
</style></head><body><div class="wrap">
  <header>
    <h1>Voice check-in</h1>
    <div class="sub">{subject} &middot; {len(records)} sessions &middot; stays on this machine</div>
  </header>
  <div class="headline{'' if findings else ' clear'}">{headline}</div>
  <div class="baseline-note">Measured against your own baseline from your first
    {n_baseline} sessions. Shaded band is one standard deviation; the dashed line
    is your baseline average.</div>
  {body}
  <footer>
    <strong>This describes what changed, not why.</strong> Ordinary causes are the
    common ones: a head cold, a different microphone, the time of day, the room.
    Nothing here is a diagnosis. Sessions scored: {", ".join(later) or "none yet"}.
  </footer>
</div></body></html>'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sessions")
    ap.add_argument("--context", default="context.jsonl")
    ap.add_argument("--out", default="report.html")
    ap.add_argument("--baseline", type=int, default=3)
    ap.add_argument("--z", type=float, default=2.0)
    ap.add_argument("--persist", type=int, default=2)
    args = ap.parse_args()

    context = load_context(args.context)
    for subject, records in load(args.sessions).items():
        stats, findings = analyse(records, args.baseline, args.z, args.persist)
        if stats is None:
            print(f"{subject}: not enough baseline sessions"); continue
        html = build(subject, records, stats, findings, context, args.baseline)
        out = args.out if len(load(args.sessions)) == 1 else f"{subject}_{args.out}"
        with open(out, "w") as fh:
            fh.write(html)
        print(f"wrote {out}  ({len(findings)} findings)")


if __name__ == "__main__":
    main()
