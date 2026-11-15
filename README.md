# Baseline Drift

**Team Ground State &middot; NASA Space Apps 2026 &middot; Create Health Monitoring Software for Astronauts**

A daily voice check-in that compares each astronaut to their own baseline, runs
entirely offline, and never claims to know why something changed.

On a Mars transit, mission control is twenty minutes away and sometimes
unreachable. Crews carry most of the responsibility for noticing change in
themselves, using the least reliable observer available: a person judging their
own condition. Baseline Drift gives them a measurement instead.

## Try it

There are three ways in, from least to most effort.

**1. Online preview, nothing to install.** Open
<https://acmross.github.io/baseline-drift/try/>. There you can:

- Explore the Report and Trends views for a sample crew member. That data is
  simulated and labelled as such: 36 made-up check-ins across ten weeks.
- Switch to real check-ins recorded by a team member on her own laptop. The
  numbers and dates are real; her recordings and check-in answers are not
  published.
- Open any session to see its measurements, and delete one to see how that
  works (it comes back when you reload).
- Go through a check-in yourself: record the three takes, play them back and
  answer the questions. The audio stays in your browser tab and is discarded.
  Your voice is not measured there, because measuring needs the pipeline
  running on your own machine.

**Hosted demo, the real pipeline with nothing to install.** The hosted demo
runs the same app and the same Praat measurements on a small demo server, so
you can record a few check-ins and get your own numbers back. It is the one
version that sends a recording off your device, and it says so on the page:
your recordings, numbers and check-in answers sit under a random ID only your
browser has, so you can play them back and delete them, and everything is
deleted automatically after two hours without use. The server sleeps when idle, so the first load can take about a minute.
`Dockerfile` and `render.yaml` are what it runs from.

**2. The real app on macOS or Linux.** Needs Python 3.

    git clone https://github.com/acmross/baseline-drift.git
    cd baseline-drift
    python3 -m pip install -r web/requirements.txt
    python3 -m uvicorn web.server:app --host 127.0.0.1 --port 8899

Then open <http://127.0.0.1:8899>. Record the three takes, save, tick the
check-in, and open the report. Three sessions build your baseline; the fourth is
the first one scored. Everything you record stays in `web/data/` on your
machine. The app also has a "See a sample report" button that shows the same
simulated crew member as the online preview.

**3. The real app on Windows.** Download `BaselineDrift.exe` from the
[releases page](https://github.com/acmross/baseline-drift/releases) and run it.
It starts the same local app and opens your browser.

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
three of four crew below the glucose reference range at R+45, which is almost
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

## Use of AI tools

Declared per NASA Space Apps requirements.

**In building this project.** Claude (Anthropic) was used substantially: it
wrote most of the Python in `pipeline/` and `validation/`, drafted this README
and `FRONTEND.md`, drafted the slide deck, and was used to find and summarise
the literature and NASA datasets cited here. Every figure quoted from a paper
or dataset was checked against the primary source, and the OSD-575 results in
`validation/` were produced by running the committed code on the committed
data, not written by hand. Design decisions, scope, and the project direction
are the team's.

**Inside the product.** `checkin_agent.py` can optionally use a small local
language model through Ollama to phrase the check-in questions and extract
structured answers from free text. It runs on the local machine with no
network access, it is given no interpretive role, and the tool works fully
without it (`--backend none`).

**Not used.** No AI-generated images, audio or video appear in this project.
No NASA branding or design elements were generated or modified. The synthetic
audio in `make_test_audio.py` is procedurally generated signal, not a
generative model, and is clearly labelled as a test fixture rather than speech.

## Data

NASA Open Science Data Repository, [OSD-575](https://osdr.nasa.gov/bio/repo/data/studies/OSD-575):
SpaceX Inspiration4 Blood Serum Metabolic Panel and Immune/Cardiac Cytokine
Arrays. DOI [10.26030/mc5d-p710](https://doi.org/10.26030/mc5d-p710).
PI Christopher Mason, Weill Cornell Medicine.
