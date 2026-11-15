"""
Generates synthetic check-in audio so the pipeline can be verified before
anyone records anything. NOT a substitute for real recordings: it is a
source-model buzz, not speech. Its only job is to prove the code runs and
that the detector fires when a feature genuinely moves.

Usage: python3 make_test_audio.py <outdir>
"""
import sys, os
import numpy as np
import soundfile as sf

SR = 16000
RNG = np.random.default_rng(7)


def utterance(f0, amp, jitter, pause_frac, dur=6.0):
    """A pulse-train vowel with pauses: crude, but it has F0, energy and silence."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    # wobble the period to create jitter
    inst_f0 = f0 * (1 + jitter * RNG.standard_normal(n).cumsum() / np.sqrt(n))
    phase = 2 * np.pi * np.cumsum(inst_f0) / SR
    sig = sum(np.sin(k * phase) / k for k in range(1, 12))   # harmonic stack
    sig *= amp
    # carve out pauses in blocks so the pause ratio is controllable
    block = int(SR * 0.4)
    gate = np.ones(n)
    for start in range(0, n, block * 2):
        if RNG.random() < pause_frac:
            gate[start:start + block] = 0.0
    sig *= gate
    sig += 0.001 * RNG.standard_normal(n)
    return (sig / np.abs(sig).max() * 0.9).astype(np.float32)


def main(outdir):
    os.makedirs(outdir, exist_ok=True)
    plan = [
        # baseline: three sessions, same speaker, normal variation
        ("day1", 118, 0.80, 0.010, 0.15),
        ("day2", 121, 0.82, 0.011, 0.17),
        ("day3", 119, 0.79, 0.010, 0.14),
        # then a sustained shift: lower pitch, quieter, more pausing
        ("day4", 104, 0.55, 0.019, 0.42),
        ("day5", 102, 0.52, 0.021, 0.45),
        ("day6", 105, 0.54, 0.020, 0.40),
    ]
    for label, f0, amp, jit, pause in plan:
        path = os.path.join(outdir, f"{label}.wav")
        sf.write(path, utterance(f0, amp, jit, pause), SR)
        print("wrote", path)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "test_audio")
