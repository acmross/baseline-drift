"""
Merge per-task acoustic features into one session record.

The protocol assigns features by task: the sustained vowel carries jitter,
shimmer and harmonic-to-noise ratio; the fixed passage carries duration, pitch,
loudness, pausing and the voiced-rate proxy. Mixing sources would silently
change the baseline, so the mapping is explicit here and tested.
"""
PASSAGE_FEATURES = (
    "duration_s", "f0_mean_hz", "f0_sd_hz", "intensity_db",
    "pause_ratio", "voiced_rate_hz",
)
VOWEL_FEATURES = ("jitter_local", "shimmer_local", "hnr_db")
FEATURE_ORDER = PASSAGE_FEATURES + VOWEL_FEATURES


def merge_session_features(vowel: dict, passage: dict) -> dict:
    """Return one feature dict with None for any unavailable measurement."""
    merged = {feature: passage.get(feature) for feature in PASSAGE_FEATURES}
    merged.update({feature: vowel.get(feature) for feature in VOWEL_FEATURES})
    return {feature: merged.get(feature) for feature in FEATURE_ORDER}
