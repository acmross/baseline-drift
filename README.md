# Baseline Drift

**Team Ground State &middot; NASA Space Apps 2026 &middot; Create Health Monitoring Software for Astronauts**

A daily voice check-in that compares each astronaut to their own baseline, runs
entirely offline, and never claims to know why something changed.

On a Mars transit, mission control is twenty minutes away and sometimes
unreachable. Crews carry most of the responsibility for noticing change in
themselves, using the least reliable observer available: a person judging their
own condition. Baseline Drift gives them a measurement instead.

## What it does

The astronaut records a short check-in and answers a few questions. The tool
extracts eight acoustic features, compares them to that person's own earlier
sessions, and reports what moved, by how much, and for how long.

It does **not** detect fatigue, stress, or mood. Inferring an emotional or
cognitive state from voice is an open research problem with modest published
effect sizes. We report that a measurement moved relative to baseline and leave
interpretation to the crew member. That is a deliberate scope choice.

## Why baselines, not norms

Spaceflight shifts everyone's numbers, so a population "normal range" is the
wrong yardstick. A per-person baseline also absorbs accent, sex and individual
voice differences for free.

## Three gates

A finding is reported only when all three pass. Each was added because the
previous set let noise through:

| Stage | Result |
|---|---|
| z-score alone, on NASA OSD-575 | 65 flags in 272 comparisons. Noise. |
| plus clinical reference range | 11 flags, and they look real. |
| z + minimum change, on a synthetic voice control | still fired on one isolated session. |
| plus persistence across sessions | silent on the control, while true drift still fires. |

## Validated on NASA data

`validation/` runs the same detector on **OSD-575**, the Inspiration4 blood
serum metabolic panel: four astronauts, three pre-flight and four post-flight
samples each, nineteen analytes. That pre/post structure is the same shape as
the voice baseline logic, so the detector transfers directly.

It also surfaced four data-quality problems worth knowing about, including an
assay ceiling, a reference range that shifts mid-study for one subject, and
three of four crew below the glucose reference range at R+45 — which is almost
certainly sample handling, not physiology. The detector fired correctly and the
cause was logistics. That is the argument for never naming a cause.

## Layout

    pipeline/     voice capture to report. Python, runs offline.
    validation/   the NASA OSD-575 run.
    web/          the crew-facing interface.
    FRONTEND.md   spec for the interface.

## Running it

    pip install praat-parselmouth soundfile

Verify the chain before recording anything:

    cd pipeline
    python3 make_test_audio.py audio
    for d in day1 day2 day3 day4 day5 day6; do
      python3 voice_features.py CDR-01 $d audio/$d.wav
    done
    python3 voice_drift.py sessions.jsonl

Real sessions follow `pipeline/recording_protocol.md`. Three sessions build the
baseline; everything after is scored against it.

## Constraints that are not preferences

- **No network calls.** The entire premise is that this runs with mission
  control unreachable. One font CDN undoes it.
- **Descriptive language only.** Every output is a measurement plus a duration.
  Never a diagnosis.
- **Calibrate before trusting.** The `MIN_CHANGE` thresholds shipped here are
  placeholders. Measure your own session-to-session noise floor first.

## Data

NASA Open Science Data Repository, [OSD-575](https://osdr.nasa.gov/bio/repo/data/studies/OSD-575):
SpaceX Inspiration4 Blood Serum Metabolic Panel and Immune/Cardiac Cytokine
Arrays. DOI [10.26030/mc5d-p710](https://doi.org/10.26030/mc5d-p710).
PI Christopher Mason, Weill Cornell Medicine.
