"""Edge silence must not count as pausing or change the speech duration."""
import numpy as np
import soundfile as sf

from pipeline.voice_features import extract

SR = 16000


def tone(seconds):
    t = np.arange(int(SR * seconds)) / SR
    return 0.5 * sum(np.sin(2 * np.pi * 120 * k * t) / k for k in range(1, 8))


def write(path, lead, speech, tail):
    quiet = lambda s: 1e-4 * np.random.default_rng(1).standard_normal(int(SR * s))
    sig = np.concatenate([quiet(lead), tone(speech), quiet(tail)]).astype(np.float32)
    sf.write(path, sig, SR)


def test_edge_silence_is_trimmed(tmp_path):
    tight, padded = tmp_path / "tight.wav", tmp_path / "padded.wav"
    write(tight, 0.0, 3.0, 0.0)
    write(padded, 2.0, 3.0, 8.0)
    a, b = extract(tight), extract(padded)
    assert abs(b["duration_s"] - 3.0) < 0.4
    assert b["pause_ratio"] < 0.1
    assert abs(a["pause_ratio"] - b["pause_ratio"]) < 0.05
    assert abs(a["voiced_rate_hz"] - b["voiced_rate_hz"]) / a["voiced_rate_hz"] < 0.1


def test_internal_pause_is_kept(tmp_path):
    path = tmp_path / "gap.wav"
    quiet = 1e-4 * np.random.default_rng(2).standard_normal(SR * 2)
    sig = np.concatenate([tone(2.0), quiet, tone(2.0)]).astype(np.float32)
    sf.write(path, sig, SR)
    feats = extract(path)
    assert 0.2 < feats["pause_ratio"] < 0.5
    assert abs(feats["duration_s"] - 6.0) < 0.4
