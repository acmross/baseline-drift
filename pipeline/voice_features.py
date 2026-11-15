"""
Baseline Drift: acoustic feature extraction for a daily voice check-in.

One recording in, one feature dict out. Nothing here interprets anything;
interpretation is voice_drift.py's job, and even there it stays descriptive.

Usage:
    python3 voice_features.py <subject> <session_label> <audio.wav> [more.wav ...]
        appends one JSON record per file to sessions.jsonl

Requires: praat-parselmouth, soundfile
"""
import sys, json, statistics as st
import numpy as np
import parselmouth
from parselmouth.praat import call

# Praat pitch floor/ceiling. Wide enough for any adult voice; narrowing these
# per speaker after the baseline sessions would improve F0 stability.
PITCH_FLOOR, PITCH_CEILING = 75.0, 500.0
SILENCE_DB = 25.0   # dB below peak that counts as silence, for the pause ratio


def extract(path):
    snd = parselmouth.Sound(str(path))
    dur = snd.get_total_duration()

    pitch = snd.to_pitch(pitch_floor=PITCH_FLOOR, pitch_ceiling=PITCH_CEILING)
    f0 = pitch.selected_array['frequency']
    voiced = f0[f0 > 0]

    intensity = snd.to_intensity(minimum_pitch=PITCH_FLOOR)
    db = intensity.values[0]
    db = db[np.isfinite(db)]

    # Jitter and shimmer need a point process of glottal pulses.
    pp = call(snd, "To PointProcess (periodic, cc)", PITCH_FLOOR, PITCH_CEILING)
    jitter  = call(pp, "Get jitter (local)", 0, 0, 1e-4, 0.02, 1.3)
    shimmer = call([snd, pp], "Get shimmer (local)", 0, 0, 1e-4, 0.02, 1.3, 1.6)

    hnr = call(snd.to_harmonicity(), "Get mean", 0, 0)

    # Pause ratio: share of frames more than SILENCE_DB below the loudest frame.
    pause_ratio = float(np.mean(db < (db.max() - SILENCE_DB))) if db.size else 0.0

    # Speech rate proxy: voiced frames per second of recording. Not true
    # syllables, but it moves with rate and is stable across sessions as long
    # as the prompt is identical, which is why the protocol fixes the passage.
    voiced_rate = len(voiced) / dur if dur else 0.0

    def clean(x):
        x = float(x)
        return x if np.isfinite(x) else None

    return {
        "duration_s":     round(dur, 3),
        "f0_mean_hz":     clean(st.mean(voiced)) if voiced.size else None,
        "f0_sd_hz":       clean(st.pstdev(voiced)) if voiced.size > 1 else None,
        "intensity_db":   clean(db.mean()) if db.size else None,
        "jitter_local":   clean(jitter),
        "shimmer_local":  clean(shimmer),
        "hnr_db":         clean(hnr),
        "pause_ratio":    round(pause_ratio, 4),
        "voiced_rate_hz": round(voiced_rate, 3),
    }


def main(argv):
    if len(argv) < 4:
        print(__doc__); return 1
    subject, session = argv[1], argv[2]
    with open("sessions.jsonl", "a") as out:
        for path in argv[3:]:
            feats = extract(path)
            rec = {"subject": subject, "session": session, "file": path, "features": feats}
            out.write(json.dumps(rec) + "\n")
            print(f"{subject} {session} {path}")
            for k, v in feats.items():
                print(f"    {k:16} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
