"""The three takes supply different features; merge must respect the split."""
from web.feature_merge import merge_session_features

VOWEL = {"jitter_local": 0.01, "shimmer_local": 0.06, "hnr_db": 20.0,
         "f0_mean_hz": 999.0}
PASSAGE = {"duration_s": 31.0, "f0_mean_hz": 120.0, "f0_sd_hz": 21.0,
           "intensity_db": 85.0, "pause_ratio": 0.04, "voiced_rate_hz": 95.0}


def test_vowel_supplies_voice_quality():
    merged = merge_session_features(VOWEL, PASSAGE)
    assert merged["jitter_local"] == 0.01
    assert merged["shimmer_local"] == 0.06
    assert merged["hnr_db"] == 20.0


def test_passage_supplies_rate_and_pitch():
    merged = merge_session_features(VOWEL, PASSAGE)
    assert merged["f0_mean_hz"] == 120.0
    assert merged["pause_ratio"] == 0.04
    assert merged["voiced_rate_hz"] == 95.0


def test_missing_values_become_none():
    merged = merge_session_features({}, {})
    assert merged["jitter_local"] is None
    assert merged["f0_mean_hz"] is None
