# Baseline Drift: How We Win NASA Space Apps 2026

**Project:** Baseline Drift (team Ground State) — daily voice check-in with per-person baseline drift detection
**Challenge:** Create Health Monitoring Software for Astronauts on Space Missions (Intermediate)
**Event:** NASA International Space Apps Challenge 2026, "The Next Frontier" — Nov 14–15, 2026
**Submission:** Sunday, Nov 15, 11:59 PM local event time (save is not submit)
**Team:** Amanda (CS PhD, speech/audio; design and pitch lead) · Ruben (Python, graphics, AI) · front-end developer (recruiting)
**Status:** MVP code exists (`ground-state-handoff/code/`), UI and demo not yet built

---

## 1. Executive summary

We build a daily voice check-in for astronauts that compares each person to their own baseline and flags sustained drift, without claiming to diagnose mood or fatigue.

Long-duration crews increasingly carry responsibility for spotting changes in themselves. On a Mars transit, mission control is 20 minutes away and sometimes unreachable, and self-report suffers from survey fatigue and real incentives not to disclose symptoms. Baseline Drift turns a signal crews already produce — their voice — into a private, offline, crew-facing instrument: record a short check-in, extract acoustic features, compare against that person's own established baseline, and report only sustained, unexplained movement in plain language.

**Why we win:** a working pipeline, a validated method, a defensible scope, and a clear story. Most teams will demo a dashboard of simulated vitals. We will demo a real detector running on real recordings, validated against real NASA data, with an honesty position that survives judge questioning. Depth beats breadth at this event.

**Win thesis in one line:** existing work predicts crew state *for mission control*; Baseline Drift reports to *the crew member*, offline, comparing the person to themselves — and we prove the method's discipline on NASA's own data before applying it to voice.

---

## 2. Challenge fit and judging strategy

### What the challenge asks

Build health monitoring software that gathers health indicators and enables astronauts to evaluate and act on the status of their health during long-duration missions, where radiation, isolation and confinement, altered gravity, and a closed hostile environment drive immune changes, bone loss, cardiovascular events, and behavioral health problems.

### Why Baseline Drift answers it

- **A real signal, not a mock panel.** Voice is a physiological and behavioral channel crews already use daily (audio logs). We measure it, not invent it.
- **A crew-facing tool.** The challenge emphasizes astronauts evaluating and acting on their own status. Baseline Drift is built for the crew member first, not for a ground dashboard.
- **Honest health monitoring.** We report measurements and durations, never diagnoses. The tool supports the crew member's own judgment and the private medical conference that already exists.
- **Grounded in NASA evidence.** HERA analog-mission work, aviation speech-fatigue literature, and OSD-575 method validation anchor every claim we make.

### Judging narrative

Judges evaluate use of NASA data, originality, impact, execution, and communication. Our project maps to each:

| What judges look for | What we show |
| --- | --- |
| Use of NASA data | OSD-575 Inspiration4 metabolic panel runs through the identical deviation logic as the demo, with the DOI cited and data-quality caveats surfaced. |
| Originality | Crew-facing, offline autonomy framing; per-person baseline with a three-gate rule; explained-versus-unexplained drift split. |
| Impact | Turns "I feel off" into "my speech has been slower and more halting five days running" — actionable in a private conference, viable at Mars latency. |
| Execution | Working end-to-end pipeline, browser check-in, report screen, reproducible demo data, null-case honesty. |
| Communication | Seven-slide arc, working public links, prepared answers to the four hardest questions. |

### What we deliberately do not claim

We do not detect fatigue, stress, or mood. Inferring emotional or cognitive state from voice is an open research problem and published effect sizes are modest. We report that a measurement moved relative to baseline and leave interpretation to the crew member. This is a scope decision, stated in the pitch, not a gap.

The bodysuit stays in the pitch as the future sensor layer. The challenge asks for software, and integrated circuits in a garment is not a weekend build.

---

## 3. Users and use context

**Primary user:** a crew member on a long-duration mission, alone with their health status for hours or days at a time.

**Device:** the Station Support Computer (Ops LAN laptop) — the machine where private medical conferences already happen and which sits deliberately off the station's command and control bus. Tablets are used daily on ISS but not yet for critical operations; personal smartphones only became permissible from Crew-12 and Artemis II, and NASA's review stresses segmenting them from networks carrying crew health data. Phone is future work. Build for a laptop screen, keyboard, and built-in microphone.

**Environment:** offline by premise. Mission control may be unreachable; the tool must run with the network down, no cloud, no auth, no CDN, no external fonts.

**Adjacent channel:** the ground channel already exists — weekly private medical conferences with flight surgeons and biweekly psychological conferences, protected under the Privacy Act. We are not building the alerting channel. We are building what the crew member brings to it.

---

## 4. Product scope (MVP) and non-goals

### MVP: one page, three states

1. **Record.** Three takes per session, in order: a 5-second sustained "ah", a fixed passage read aloud (~30 seconds, shown on screen), and 60 seconds of free speech answering a fixed prompt. Mission-day tag. Microphone level meter so nobody discovers a muted mic after the take.
2. **Check-in.** Six skippable free-text questions from `checkin_agent.py`: cold/congestion, cough, sleep hours, headache, posture, setup changed, plus anything else. Answers produce `context.jsonl` with an `explains` map — which acoustic features each reported cause could account for.
3. **Report.** The output of `voice_drift.py`, one screen: per feature, a plain-language line, the numbers, a sparkline against the baseline band, and whether the change has a reported explanation. Unexplained findings surface first.

### Core engine

- Eight acoustic features per recording via Praat/parselmouth: mean F0, F0 variability, intensity, jitter, shimmer, harmonic-to-noise ratio, pause ratio, and a voiced-rate proxy.
- Per-person baseline from the first three sessions; z-score per feature for everything after.
- Three gates: z ≥ 2.0 against the person's own baseline, a minimum meaningful change in the feature's natural units, and persistence on at least two consecutive sessions in the same direction.
- JSONL storage on disk. No database, no auth, no cloud dependency.
- Local server bound to `127.0.0.1` (FastAPI or Flask) so the browser can call the pipeline. Still fully offline; say "localhost" in the demo, never "cloud".

### Non-goals (roadmap and pitch only)

- Bodysuit or wearable sensor fusion (future input stream).
- Cloud sync, ground transmission, clinician dashboard.
- Clinical diagnosis, mood or fatigue classification, population norms.
- Phone or tablet client.

---

## 5. UX and UI specification

### Screen 1: Record

- Step indicator: ah → passage → free speech.
- Large, readable passage with a copy-checked character count; identical text every session.
- Recording state with elapsed timer, level meter, and a clear stop control.
- On completion: per-take status (captured, too quiet, too short) and a single primary action to continue.
- Edge states: microphone permission denied, no input device, silent take, interrupted take. Every one has a plain-language recovery path.

### Screen 2: Check-in

- One question at a time, free text, visible label, skip available.
- No dropdown-only fields; free text is itself recorded and parsed.
- Progress indicator and back navigation.
- Helper text explaining that answers only contextualize measurements — they never suppress a finding silently.

### Screen 3: Report

Ordering is the product: **unexplained drift first**, then explained/accounted findings, then stable features.

Each finding shows:

- The measurement and duration: "Vocal energy is 1.8 standard deviations below your baseline, third consecutive day."
- The numbers and baseline band.
- A sparkline of the feature across sessions.
- A plain-language note when a reported cause (cold, cough, setup change, non-upright posture, short sleep) already accounts for the movement.

Also designed, not just the happy path:

- **Baseline building:** sessions 1–3 show "building your baseline — 2 of 3 sessions" and never a finding.
- **Stable:** an explicit "nothing sustained moved" state, not an empty page.
- **Empty:** no sessions yet, with the next action.
- **Loading:** extraction and scoring feedback with reserved space, no layout shift.
- **Error:** failed extraction, corrupt session file, server unavailable, with retry.

### Design principles

- **Descriptive language only.** Every string is a measurement plus a duration. Never "you appear fatigued", never a diagnosis. This is the core design position.
- **"Your baseline", never "normal range".** Wording reinforces the per-person method.
- **Crew trust.** No network calls in code or assets; readable source; the crew member can inspect and delete their own data. Provable privacy, not promised privacy.
- **Accessibility (WCAG 2.2 AA).** 4.5:1 text contrast, visible focus states, 44px targets, semantic headings, labeled inputs, keyboard-complete flows, reduced-motion respected.
- **Consistent component system.** One spacing scale, one radius scale, one elevation scale, reusable button/input/card variants.
- **No AI-design tells.** No default violet-to-blue gradient, no glassmorphism decoration, no neon glow, no emoji icons, no four identical cards, no center-everything layout. Utilitarian, calm, evidence-first.

---

## 6. System architecture and data contracts

```
Browser UI (offline page)
  Record / Check-in / Report
        │  fetch to 127.0.0.1 only
        ▼
Local FastAPI/Flask server
  ├─ voice_features.py   wav → 8 acoustic features → sessions.jsonl
  ├─ voice_drift.py      three gates → findings (JSON)
  ├─ checkin_agent.py    questions → context.jsonl (explains map)
  └─ make_report.py      findings → report view
```

### Browser audio: the one trap that costs an hour

`MediaRecorder` produces WebM/Opus, not WAV, and Praat needs PCM WAV. Either capture raw samples through an `AudioWorklet` and write the 44-byte WAV header, or decode and re-encode server-side. Opus is lossy and moves the exact features we measure; renaming the file is not a fix.

### Data contracts

`sessions.jsonl`, one object per line:

```json
{"subject":"AMANDA","session":"day1","file":"day1_passage.wav",
 "features":{"duration_s":31.2,"f0_mean_hz":119.3,"f0_sd_hz":21.4,
 "intensity_db":85.0,"jitter_local":0.0104,"shimmer_local":0.061,
 "hnr_db":54.5,"pause_ratio":0.0385,"voiced_rate_hz":95.1}}
```

`context.jsonl`, one object per line:

```json
{"subject":"AMANDA","session":"day1",
 "answers":{"cold_or_congestion":true,"cough":false,"sleep_hours":7.0,
            "headache":null,"posture":"sitting","setup_changed":false,
            "anything_else":null,"cold_or_congestion_raw":"yeah a bit stuffy"},
 "explains":{"f0_mean_hz":["cold_or_congestion"],"hnr_db":["cold_or_congestion"]},
 "backend":"none"}
```

Any feature may be `null`. Short or silent recordings produce nulls; the UI must handle them.

---

## 7. Detection method and validation

### Five stages, each independently testable

1. **Record.** Scripted passage plus 60 seconds of free speech, tagged with a mission day.
2. **Extract features.** Praat via parselmouth (or openSMILE, which the NASA HERA team used).
3. **Build the baseline.** First three sessions per person become the reference distribution: mean and standard deviation per feature. No training, no labels.
4. **Score the drift.** Three gates, all required:
   - z ≥ 2.0 against the person's own baseline;
   - change exceeds a minimum meaningful size in the feature's natural units;
   - same feature moves the same direction on at least two consecutive sessions.
5. **Report.** Descriptive findings only, unexplained first.

### Validated on NASA data, and it changed the design

Running the deviation logic on the OSD-575 Inspiration4 metabolic panel (four crew, three pre-flight and four post-flight samples each), a z-score threshold alone flagged **65 of 272 comparisons** (24%). That is noise. A three-sample baseline produces a tiny unstable standard deviation, so clinically meaningless changes blow up — one crew member's calcium moved 10.1 to 9.8 and scored z = -3.0.

Adding the second gate cut that to flags that look real, including a crew member whose glucose hit 44 against a 65–99 range. Then on synthetic voice control data where nothing changed, two gates still fired on one isolated session; adding persistence silenced the control completely while the true drift case still fired on all five affected features.

| Stage | Result |
| --- | --- |
| z-score alone, OSD-575 | 65 flags in 272 comparisons. Noise. |
| plus reference range, OSD-575 | 11 flags, and they look real. |
| z plus minimum change, synthetic voice control | still fired on one isolated session. |
| plus persistence, same control | silent, while true drift still fires. |

Every gate exists because the previous set let noise through. That progression is a slide.

### Calibration

The `MIN_CHANGE` thresholds shipped in the code are placeholders. Before trusting output, record the same passage several times in one sitting, measure the spread of each feature, and set each threshold above that noise floor. Too low reproduces the OSD-575 false-positive problem; too high detects nothing. Calibration is a named task in the schedule, not an afterthought.

---

## 8. Data plan and demo recordings

### The baseline must be rebuilt in orbit

In microgravity the head-to-foot hydrostatic pressure gradient is lost, producing a cephalad fluid shift, facial edema, and nasal stuffiness. Across 71 ISS astronauts, 85% reported a sinonasal event and 75% nasal congestion, most in the first week. An Earth pre-flight baseline compared against in-flight recordings would show every crew member permanently drifted from day one — adaptation, not illness. The baseline is re-established in orbit once adaptation settles. Say this in the pitch; it separates a team that thought about deployment from one that did not.

### Posture, honestly

Sitting versus standing does not measurably change a healthy voice; a 2025 study of 30 untrained speakers found no significant difference in any voice range profile parameter. Reclined and supine are different and do change vocal tract volume, F0, and respiratory kinematics. The check-in records posture but only lets non-upright positions account for drift. Time of day is hygiene in the protocol, not a verified control.

### Our own recordings

We record ourselves. Honest synthetic demo data beats pretending we have astronaut audio, and a judge will respect the distinction if we name it.

Every session uses the same two tasks — comparing free speech to scripted speech corrupts the baseline:

- A fixed passage read aloud, roughly 30 seconds, identical every time.
- 60 seconds of free speech answering a fixed prompt, such as what you worked on today.

Target six sessions each across the weekend, spaced a few hours apart, labelled mission days 1–6. Three establish the baseline; three test the drift logic. Record on the same device and microphone throughout; changing hardware mid-weekend shifts every feature and looks exactly like drift.

To prove the flag fires, one of us records a late-night session genuinely tired and lets the pipeline find it rather than tuning the threshold until it does. If it does not fire, that is a real result and we report it as one. A demo that admits a null case is more credible than one that never fails.

---

## 9. Privacy and governance position ("who sees it")

The crew member sees everything. Nothing leaves the habitat automatically.

**Why reporting to the ground would break the tool.** The National Academies' *Safe Passage* report documents astronauts' unique pressure to keep medical information private — disclosing may jeopardize a chance to fly again, and an atmosphere that equates symptoms with poor performance suppresses reporting, which blocks establishing physiological norms at all. A monitoring tool that transmits to the ground inherits that incentive the day it ships: crews would stop using it, or learn to perform for it.

**What it changes.** It turns "I feel a bit off" into "my speech has been slower and more halting for five days, and I haven't reported a cold." Far easier to raise in a conference already on the calendar.

**The honest tension.** Crew-held means that if someone deteriorates and chooses not to raise it, nobody catches it. That is a real safety cost. Middle grounds worth naming rather than solving: crew-controlled sharing, or crew-level aggregates with no individual attribution. We pick autonomy because the alternative suppresses the honesty the tool depends on, and we say so plainly.

**The design does not depend on crew honesty.** Keeping it local removes a known disincentive but does not guarantee candor. We do not need to win that argument: the acoustic channel requires no cooperation. A concealed cold makes voice-quality drift arrive with no reported explanation, pushing it into the bucket the report highlights rather than the one it suppresses. Honesty makes the tool more precise; concealment makes it more insistent. It fails safe either way.

**It matters more the further out you go.** A weekly real-time conference stops being possible on a Mars transit. The ground channel degrades exactly as the need grows.

---

## 10. Demo and pitch plan

The demo is capped at either 7 slides or a video of 30 seconds or less. Take the slides: thirty seconds cannot carry the setup, and slides let a judge sit on the before-and-after as long as they want. The longer walkthrough lives behind the separate Project link.

1. **Title.** Baseline Drift (team Ground State), the challenge, the team.
2. **The problem.** On a Mars transit, mission control is 20 minutes away and sometimes unreachable. Crews must spot changes in themselves, and self-reports suffer survey fatigue and disclosure incentives.
3. **The insight.** Crews already record daily audio logs; NASA has shown speech from analog missions predicts crew functioning; nobody has built the crew-facing version.
4. **How it works.** The five-stage pipeline and three gates in one diagram, offline laptop target.
5. **The result.** Baseline day against drifted day, with the report screen. Embed both audio clips if the format allows.
6. **The honesty beat.** We do not diagnose. We compare you to you and report what moved.
7. **What is next.** The sensor layer as a second input stream; validation against reaction-time testing.

### Questions a judge will likely ask

- *Can you really tell mood from voice?* No, and we do not try. Here is what we do instead.
- *What about accents, colds, different languages?* A per-person baseline absorbs all three, which population norms do not. A head cold is a real limitation and we flag it as a known confound.
- *How much data do you need?* Three sessions to baseline — a genuine strength over supervised approaches needing labelled corpora.
- *What is novel here?* The autonomy framing. Existing work predicts crew state for mission control. Ours reports to the crew member, offline.

### Links

Both links must be public, with no password, permission, or registration. Test them in a private browser window before submitting; a link that only works while signed in is the most common way a finished project loses.

---

## 11. Team, roles, and 48-hour execution plan

**Skills on the team:** speech and audio analysis (PhD-level), solution design, pitching, video, Python, graphics, AI. **Gap:** front-end developer to build the interface — actively recruiting. No space background required.

Ruben joins once he is home, so the first two blocks are solo. Each block has a gate: if the gate is not met, cut scope rather than slipping the block.

| Block | Amanda | Ruben | Gate |
| --- | --- | --- | --- |
| Sat evening | Register team, record baseline session 1, get audio into Python | Travelling | A .wav file produces a pitch number |
| Sat late | Feature extraction working end to end on one file | Joins, sets up repo and front-end shell | All 8 features print for one recording |
| Sun morning | Baseline and z-score logic, drift rule, calibration pass | Recording UI, session storage | Three sessions in, drift flag fires correctly |
| Sun midday | Report screen wording and chart | Wire front end to pipeline | A fake drifting crew member renders a full report |
| Sun afternoon | Build the 7 slides, write the 50–200 word summary and project details | Slides, architecture diagram | Demo uploaded and opens in a private window |
| Sun evening | Buffer and submit | Buffer and submit | Submitted with time to spare |

The buffer block is not optional. Space Apps submissions close hard; the most common way a finished project loses is an unsubmitted form.

**Cut order if behind:** trend sparklines → in-browser recorder (demo from pre-recorded files instead) → second crew member. **Never cut:** the baseline/three-gate logic, the offline constraint, descriptive wording, the explained-versus-unexplained split, or the honesty beat.

---

## 12. Risks and mitigations

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| Front-end gap leaves the demo unusable | Medium | Recruit early; fallback is a minimal static report rendered by `make_report.py` from pre-recorded sessions. |
| `MIN_CHANGE` placeholders produce false positives or silence | High | Calibration block Sunday morning on repeated same-sitting recordings; report thresholds used. |
| Browser audio trap (Opus vs WAV) burns hours | High | AudioWorklet PCM capture or server-side re-encode; smoke-test a take end-to-end Saturday night. |
| Fewer than 3 baseline sessions per person | Medium | Use pre-recorded sessions and label mission days; baseline requirement stays intact. |
| Genuine drift case does not fire | Medium | Report as a null result; still present the control-case result and the OSD-575 progression. |
| Judge challenges "vibes-based health AI" | Medium | The honesty beat, descriptive wording, and OSD-575 validation are first-class slide content. |
| Local event/deadline confusion | Medium | Confirm registered local event and its time zone; submit with buffer, not at 23:59. |
| AI-assistance declaration missed | Medium | Declare SI tools in Project Information; watermark generated assets; list external resources. |
| Offline premise broken by a stray font/CDN call | Low | No external requests; bundle fonts or system stack; verify with network disabled. |

---

## 13. Submission checklist

Submission closes **Sunday, November 15 at 11:59 PM local event time**. Saving is not submitting. Only the final "Submit for Judging" click is reviewed; no exceptions after the deadline.

Four form sections:

- **Project Summary.** Project name and a 50–200 word summary (1500-character cap).
- **Project Links.** Demo (7 slides or 30-second video) and public project link, both password-free and sign-in-free.
- **Project Information.** Full project details, SI tool declaration, NASA data list.
- **Verification.** Terms, originality confirmation, all external resources listed.

### NASA data: OSD-575

Use [OSD-575](https://osdr.nasa.gov/bio/repo/data/studies/OSD-575), an Inspiration4 serum study in the Open Science Data Repository; processed data is public with no application. The file listing includes `LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv`, a clean clinical chemistry panel for four real astronauts sampled before, during, and after spaceflight.

The pre/in/post structure matches our baseline-and-drift logic, which is what makes it more than decoration: run the identical algorithm on the metabolic panel first, show it flags real spaceflight-induced change in real astronauts, then apply the same algorithm to voice. The NASA data validates the method; voice becomes the new input stream. That also answers the originality question without argument.

Nine files total, mostly small CSVs — a pandas afternoon, not an omics pipeline. Skip raw sequence data, which requires board approval.

**Lead with the metabolic panel; cytokine panels are a bonus.** The Eve Technologies panels are usable: use concentration columns and ignore percent columns (crew-average normalization lives in the percent columns). The Alamar panel is missing C003's L-44 sample and its log2 NPQ values carry no reference ranges, so the second gate has nothing to check there. The metabolic panel stays primary: Quest Diagnostics clinical chemistry with reference ranges attached, which the two-gate rule needs.

**Caveats to state, not hide.** Inspiration4 was a three-day mission (September 16–18, 2021) — changes after a short flight, not a Mars transit. The crew is two male and two female, and some reference ranges are sex-specific, itself an argument for per-person baselines. R+194 appears in the data but not in the study's own description of collected timepoints; flag it if reported.

**Four data-quality traps, each worth a sentence.** Judges reward teams who found the problems in their own data.

1. **A header breaks its own naming pattern.** Every range column is `<analyte>_range_max_<unit>` except ALT and AST (`alt_max_units_per_liter`, `ast_max_units_per_liter`). Pattern-matching code silently drops both; ours did, moving the flag count from 10 to 11 once fixed. The recovered flag is C004's AST at 48 against a 10–40 range.
2. **Haptoglobin hits an assay ceiling.** 17,907,000 appears 7 times in 28 in the Eve cardiovascular panel — saturation, not measurement. Exclude it if that panel is used.
3. **C003's reference ranges change mid-study.** Alkaline phosphatase, ALT, AST, creatinine, and calcium all shift between her pre- and post-flight draws; no other subject's do. The range gate is not a fixed yardstick for her.
4. **R+45 glucose is below range in three of four crew** (44, 36, 43 mg/dL). Spaceflight does not do that 45 days after landing; likely fasting status or sample handling. This is the best slide in the deck: the detector fires correctly, the cause is logistics rather than physiology, and that is exactly why we report what moved and let a human interpret it. A tool claiming a diagnosis would have been confidently wrong.

**Cite it as:** OSD-575, SpaceX Inspiration4 Blood Serum Metabolic Panel and Immune/Cardiac Cytokine Arrays, DOI [10.26030/mc5d-p710](https://doi.org/10.26030/mc5d-p710), PI Christopher Mason, Weill Cornell Medicine.

### SI declaration

Any AI-assisted work must be declared. Generated images and video need a visible watermark; generated audio, code, and data need acknowledgment in descriptive text and metadata. The declaration itself is not shown to judges, but judges see watermarks and metadata and evaluate originality and execution on what we identify. Declare honestly and early, not at 11 PM.

---

## 14. Open questions

- Confirm which local event we are registered under; the deadline follows its time zone.
- Confirm the front-end recruit, or lock the fallback static-report demo.
- Decide final `MIN_CHANGE` thresholds after the calibration pass; record them in the demo notes.
- Confirm slide-versus-video demo format early and build it before Sunday afternoon.
- Decide whether a second crew member is feasible or demo one subject plus the OSD-575 validation.
- Verify OSD-575 metabolic panel timepoints per crew member before quoting counts in slides.

---

## 15. Evidence and sources

| Source | What we take from it |
| --- | --- |
| [Machine Learning for Predicting Team Functioning in HERA Missions](https://ntrs.nasa.gov/citations/20260002431) (NASA NTRS) | LSTM models reach 80–91% on team functioning; static models fail on task accuracy |
| [Predicting Team Functioning in Long Term Space Missions Using Acoustic and Linguistic Measures](https://ntrs.nasa.gov/citations/20260005849) (NASA NTRS) | Balanced accuracy up to ~85% on self-reported outcomes, driven by acoustic features |
| [Field Study Evaluation of Cepstrum Coefficient Speech Analysis for Fatigue in Aviation Cabin Crew](https://rosap.ntl.bts.gov/view/dot/26637) (FAA) | Individual-baseline scoring correlated with reaction-time testing; feasibility unresolved |
| [Vocal Markers in Aviation of Workload, Stress, Fatigue, and Sleepiness](https://openaccess.cms-conferences.org/publications/book/978-1-964867-65-6/article/978-1-964867-65-6_19) | Direction of acoustic effects; fragmentation critique across 20 studies |
| [Detecting fatigue in multiple sclerosis through automatic speech analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC11427396) | AUC 0.68–0.74 for fatigue from free speech — our honest ceiling |

**Precision to keep straight:** the 80–91% figure is for team cohesion and efficacy, not individual fatigue. Never let it drift into "NASA detects fatigue from voice at 90%."

A Space Apps entry grounded in NASA's own published work scores better than one that asserts the same thing without a reference. Cite these in the submission.
