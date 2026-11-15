# Baseline Drift: front-end spec

Ruben, this is everything you need to start without reading the Python.

## What exists

A working pipeline, command line only:

    checkin_agent.py   asks the questions, writes context.jsonl
    voice_features.py  wav in, 8 acoustic features out, writes sessions.jsonl
    voice_drift.py     applies three gates, prints findings
    make_report.py     renders report.html

`report_demo.html` is a rendered example. Treat it as a reference for tone and
information hierarchy, not as a design you have to keep.

## What you are building it for

**A laptop, specifically a Station Support Computer.** Not a phone, not a tablet.
This is a design decision with reasons, so do not quietly retarget it:

- The private medical conference already happens on those laptops. Our whole
  job is giving the crew member something concrete to bring to that
  conversation. Same machine, same moment.
- The SSCs sit on the Ops LAN and are deliberately off the station's command
  and control bus. A health tool that must never touch flight systems belongs
  exactly there.
- Tablets are used daily on ISS but not for critical operations, and crew
  performance with them has not been measured.
- Personal smartphones were only allowed from Crew-12 and Artemis II onward,
  and NASA's own evaluation stresses segmenting personal devices away from
  networks carrying crew health information. That is our data. Phone is future
  work, not this build.

Practically: assume a 1366x768 or 1920x1080 laptop screen, keyboard and
trackpad, a built-in mic, and a browser. No touch targets, no responsive
breakpoints for phone widths. One person at a desk, or strapped to a wall.

## What to build

One page, three states. No router, no build step, no CDN.

**1. Record.** Three takes per session, in order: a 5-second sustained "ah", a
fixed passage read aloud (about 30s, text is in `recording_protocol.md`), and
60 seconds of free speech. Show the passage on screen for take 2. A level meter
while recording is worth the twenty minutes it costs: without one, people find
out the mic was muted after the take.

**2. Check-in.** Six questions from `checkin_agent.py`. Free-text input, not
dropdowns: the parser handles "yeah a bit" and the free text is itself recorded.
Skippable.

**3. Report.** The output of `voice_drift.py`. Per feature: a plain-language
line, the numbers, a sparkline against the baseline band, and whether the change
has a reported explanation. Unexplained findings are the ones to surface first.

## The data contract

`sessions.jsonl`, one JSON object per line:

```json
{"subject":"AMANDA","session":"day1","file":"day1_passage.wav",
 "features":{"duration_s":31.2,"f0_mean_hz":119.3,"f0_sd_hz":21.4,
 "intensity_db":85.0,"jitter_local":0.0104,"shimmer_local":0.061,
 "hnr_db":54.5,"pause_ratio":0.0385,"voiced_rate_hz":95.1}}
```

`context.jsonl`, one per line:

```json
{"subject":"AMANDA","session":"day1",
 "answers":{"cold_or_congestion":true,"cough":false,"sleep_hours":7.0,
            "headache":null,"posture":"sitting","setup_changed":false,
            "anything_else":null,"cold_or_congestion_raw":"yeah a bit stuffy"},
 "explains":{"f0_mean_hz":["cold_or_congestion"],"hnr_db":["cold_or_congestion"]},
 "backend":"none"}
```

`explains` is the whole confound mechanism: feature name to the list of reported
reasons that could account for it. If a feature is in `explains`, its finding is
already accounted for. If it is not, that is the one worth reading.

Any feature may be `null`. Handle it; short or silent recordings produce nulls.

## Two things that will cost you an hour each if nobody warns you

**Browser audio is not WAV.** `MediaRecorder` gives WebM/Opus. Praat needs PCM
WAV. Either capture raw samples through an `AudioWorklet` and write the 44-byte
WAV header yourself, or decode and re-encode before upload. Opus is lossy and
will move the exact features we measure, so do not just rename the file.

**The Python has to run somewhere.** Simplest path: a small FastAPI or Flask
server bound to `127.0.0.1`, with the page talking to it over fetch. That is
still fully offline, nothing leaves the machine, and it keeps the premise intact.
Say "localhost" rather than "server" in the demo so nobody hears "cloud".

## Hard constraints, not preferences

- **No network calls. None.** The entire pitch is that this runs with mission
  control unreachable. One Google Fonts link undoes it, and a judge will check.
  Bundle fonts or use a system stack.
- **Descriptive language only.** Every string is a measurement plus a duration.
  "Vocal energy is 1.8 standard deviations below your baseline, third
  consecutive day." Never "you appear fatigued." This is the core design
  position, not a style note.
- **Per-person baseline wording.** Never "normal range". Always "your baseline".

## If you run short on time

Cut in this order: the trend sparklines, then the in-browser recorder (demo from
pre-recorded files instead), then the second crew member. Do not cut the
explained-versus-unexplained split; that distinction is the whole argument.
