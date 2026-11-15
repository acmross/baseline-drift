"""
Baseline Drift: baseline-deviation detector, hardened against the data-quality
issues found in OSD-575. Same two-gate logic as drift2.py, plus:
  - handles the inconsistent *_max vs *_range_max header naming
  - detects and skips assay-saturated analytes (same value repeated)
  - warns when an analyte's reference range changes within one subject
Usage: python3 drift3.py <CMP_TRANSFORMED.csv>
"""
import sys, csv, re, statistics as st
from collections import Counter, defaultdict

PRE  = ['L-92', 'L-44', 'L-3']
POST = ['R+1', 'R+45', 'R+82', 'R+194']
Z_THRESHOLD = 2.0
SATURATION_MIN_REPEATS = 3

def load(path):
    rows = list(csv.reader(open(path, newline='', encoding='utf-8-sig', errors='replace')))
    return rows[0], rows[1:]

def num(x):
    try: return float(x)
    except (TypeError, ValueError): return None

def analytes(hdr):
    """Yield (stem, value_idx, min_idx, max_idx), tolerating header quirks."""
    idx = {c: i for i, c in enumerate(hdr)}
    out = []
    for stem in sorted({c.rsplit('_value', 1)[0] for c in hdr if '_value' in c}):
        if stem.startswith('egfr'):
            continue  # derived, and duplicated across two race-based variants
        v  = next((c for c in hdr if c.startswith(stem + '_value')), None)
        lo = next((c for c in hdr if c.startswith(stem + '_range_min')), None)
        hi = (next((c for c in hdr if c.startswith(stem + '_range_max')), None)
              or next((c for c in hdr if c.startswith(stem + '_max')), None))
        if v and lo and hi:
            out.append((stem, idx[v], idx[lo], idx[hi]))
    return out

def saturated(data, vi):
    """
    An analyte pinned at its own MAXIMUM repeatedly is sitting at an assay
    ceiling, not measuring. Repeats alone are not enough: clinical chemistry
    is reported to coarse precision, so sodium legitimately repeats 138.
    The tell is repetition AT the top of the observed range.
    """
    raw = [r[vi] for r in data if r[vi] not in ('', 'NA')]
    vals = [num(v) for v in raw]
    vals = [v for v in vals if v is not None]
    if len(set(vals)) < 4: return None
    top = max(vals)
    n = sum(1 for v in vals if v == top)
    return top if n >= SATURATION_MIN_REPEATS else None

def main(path):
    hdr, data = load(path)
    recs = {}
    for r in data:
        m = re.match(r'(C\d+)_serum_(.+)', r[0].strip())
        if m: recs[(m.group(1), m.group(2))] = r
    crew = sorted({k[0] for k in recs})

    skipped, flags, z_only = [], [], 0
    for stem, vi, li, hi_ in analytes(hdr):
        sat = saturated(data, vi)
        if sat:
            skipped.append((stem, sat))
            continue
        for c in crew:
            # a range that moves mid-study is not a fixed yardstick
            seen = {(recs[(c, t)][li], recs[(c, t)][hi_])
                    for t in PRE + POST if (c, t) in recs and recs[(c, t)][li]}
            range_moved = len(seen) > 1

            base = [num(recs[(c, t)][vi]) for t in PRE if (c, t) in recs]
            base = [b for b in base if b is not None]
            if len(base) < 3: continue
            mu, sd = st.mean(base), st.stdev(base)
            if sd == 0: continue

            for t in POST:
                if (c, t) not in recs: continue
                v  = num(recs[(c, t)][vi])
                lo = num(recs[(c, t)][li])
                hi = num(recs[(c, t)][hi_])
                if None in (v, lo, hi): continue
                z = (v - mu) / sd
                if abs(z) < Z_THRESHOLD: continue
                z_only += 1
                if v < lo or v > hi:
                    flags.append((c, t, stem, round(z, 1), v, (lo, hi), range_moved))

    print(f"Skipped {len(skipped)} analyte(s) at an assay limit:")
    for s, v in skipped: print(f"   {s}: pinned at {v}")
    print(f"\nGate 1 only (|z| >= {Z_THRESHOLD}): {z_only} flags")
    print(f"Gate 1 AND outside reference range: {len(flags)} flags\n")
    for c, t, stem, z, v, rng, moved in sorted(flags, key=lambda f: (f[0], POST.index(f[1]))):
        warn = "  [!] reference range changed mid-study for this subject" if moved else ""
        print(f"   {c} {t:6} {stem:24} z={z:+5}  value={v}  range={rng}{warn}")

if __name__ == '__main__':
    main(sys.argv[1])
