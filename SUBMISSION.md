# Space Apps submission content

Copy each block into the matching form field. Deadline: Sunday 15 November,
11:59 PM local time for the San Jose event. Saving is not submitting.

---

## Project Name

Baseline Drift

---

## Summary (50 to 200 words)

Astronauts on long missions carry much of the responsibility for noticing
changes in their own health, at exactly the distance where help is slowest.
Baseline Drift is a daily voice check-in that runs entirely offline on the
crew's own laptop.

The astronaut records a short sample and answers a few questions. The tool
extracts eight acoustic features, compares them against that person's own
earlier sessions rather than a population norm, and reports what moved, how
far, and for how long.

It does not diagnose. Inferring mood or fatigue from voice is an open research
problem with modest published accuracy, so we report measurements and leave
interpretation to the crew member. That discipline is also what makes the tool
useful: when a reported head cold accounts for the change, the report says so,
and what remains unexplained is the part worth reading.

We validated the detection method on NASA OSD-575, the Inspiration4 blood serum
panel, before applying it to voice. A z-score alone flagged 65 of 272
comparisons. Adding a clinical reference range gate cut that to 11. That result
shaped the final three-gate design and is reproducible from the code and data in
this repository.

---

## Project Details

**What it does.** Baseline Drift turns a daily voice check-in into a health
signal the crew member can act on. Each session has three fixed tasks: a
sustained vowel, a fixed passage read aloud, and thirty seconds of free speech
answering the same four questions. The
tool extracts eight acoustic measures (mean fundamental frequency and its
variability, intensity, jitter, shimmer, harmonic-to-noise ratio, pause ratio
and speaking rate), compares them to that person's own baseline, and reports
what changed in plain language.

**How it works: three gates.** A finding is reported only when all three pass,
and each gate exists because the previous set let noise through.

1. The z-score against this speaker's own baseline mean and standard deviation
   must reach 2.0.
2. The change must also exceed a minimum meaningful size in the feature's own
   units.
3. The same feature must move the same direction across at least two
   consecutive sessions.

We know the gates are necessary because we tested them. Running gate 1 alone on
NASA's OSD-575 clinical panel flagged 65 of 272 comparisons, roughly a quarter,
which is noise rather than detection. The cause is that a three-sample baseline
produces a small unstable standard deviation: one crew member's calcium moved
from 10.1 to 9.8 and scored z = -3.0, which is clinically meaningless. Adding
gate 2 cut 52 flags to 11. On synthetic voice data where nothing changed, gates
1 and 2 still fired on one isolated session, which is what gate 3 removes.

**The check-in, and why it matters.** A short check-in follows the recording: a
tick form in the app, or in the command-line version an optional small language
model on the same machine. It asks about congestion, cough, sleep, unusual pain,
posture and whether the recording setup changed. Each question declares which acoustic features a "yes" could plausibly
account for: upper respiratory symptoms are well established as affecting voice
quality, so a reported cold licenses movement in F0, harmonic-to-noise ratio,
jitter, shimmer and intensity. Unusual pain licenses nothing, because it has no
established acoustic signature, so it is recorded in the crew member's own
words but never used to suppress a finding.

What falls out is the useful part. In our simulated sample run, a speaker
reporting a cold
has three of five changes accounted for, while "more pausing" and "speaking
slower" survive unexplained. Those two are precisely the fatigue markers in the
aviation literature, and what a 2026 sleep-deprivation study (SOMVOICE) found
in tired speakers. A cold does not explain them.

**Why two channels.** Self-report fails when someone will not say, and the
National Academies has documented that astronauts face real pressure to withhold
medical information because disclosure may affect whether they fly again.
Acoustics fail when something benign moves the numbers. Neither is trustworthy
alone, and each covers the other's blind spot. Critically, the design does not
depend on candour: concealing a cold pushes the drift into the unexplained
column, which is the one the report highlights. It fails safe.

**What we deliberately do not do.** We do not claim to detect fatigue, stress or
mood. The published effect sizes do not support it: a clinical study detecting
fatigue from free speech reached an AUC of 0.68, and a systematic review of
twenty aviation studies found results fragmented by methodological heterogeneity
and limited ecological validity. Every output string is a measurement plus a
duration, never a diagnosis.

**Validation on NASA data.** OSD-575 is the Inspiration4 blood serum metabolic
panel: four astronauts, three pre-flight and four post-flight samples each,
nineteen analytes. That before-and-after structure is the same shape as our
baseline logic, so the detector transfers directly. Beyond validating the
method, running it surfaced four data-quality findings: a header that breaks its
own naming convention and silently drops two analytes; haptoglobin pinned at an
assay ceiling in seven of twenty-eight samples; reference ranges that shift
mid-study for one subject only; and glucose below the reference range in three
of four crew at R+45, which forty-five days after landing is far more likely to
be fasting status or sample handling than physiology. That last one is the best
argument for our design: the detector fired correctly and the cause was
logistics. A tool that had named a cause would have been confidently wrong.

**Where it runs.** On the Station Support Computer, the Ops LAN laptop that
already hosts private medical conferences and sits deliberately off the
station's command and control bus. The tool is crew-held: nothing is transmitted
automatically. NASA already operates the ground channel, with weekly private
medical conferences and biweekly psychological conferences. We are not replacing
that. We are building what the crew member brings to it, turning "I feel a bit
off" into "my speech has been slower and more halting for five days and I have
not reported a cold."

**Built with.** Python, with Praat through parselmouth for acoustic feature
extraction, the same toolchain used to derive features for NIH's Bridge2AI-Voice
dataset. The crew-facing app is one page of plain HTML, CSS and JavaScript
served by a small FastAPI process bound to 127.0.0.1 on the crew laptop, with
inline SVG charts and no external assets. It has four views: Record, Report,
Trends over days, weeks and months, and Sessions. A crew member can play back,
open and delete any of their own sessions, and restart their baseline in one
press. That matters because about three in four ISS crew are congested in their
first week in orbit, so a first-week baseline is a congested one. The app says
so and offers to restart the baseline from flight day 8. There are no network calls at runtime,
because the entire premise is that it works with mission control unreachable.

**Try it.** Three ways, all public and sign-in free. The hosted demo
(https://acmross.github.io/baseline-drift/demo/) runs the real pipeline so a
judge can record check-ins and get their own measurements back. It is the one
version that sends a recording off the device, it says so on the page, and
everything recorded there is deleted within two hours. The online preview
(https://acmross.github.io/baseline-drift/try/) opens instantly on a simulated
crew member's ten weeks of check-ins, plus real check-ins from a team member.
The repository has the app itself for macOS, Linux and Windows.

**On Earth.** The same tool fits low-bandwidth telehealth: a check-in that runs
offline on existing hardware, tracks a person against their own history rather
than a population they may not resemble, and gives them something concrete to
bring to a clinician they see rarely.

**Prior work, and what is actually new.** The signal is not speculative and we
are not claiming an empty field. NASA-funded work on the HERA isolation analog
predicted crew efficacy and cohesion at 80 to 91 percent from acoustic features
(that figure is team functioning, not individual fatigue, and we are careful not
to overstate it). Axiom Space is flying Voice in Space on private astronaut
missions, using electroglottograph measurements and scripted recordings to train
detection algorithms. NIH's Bridge2AI-Voice has assembled 48,000 recordings
using the same Praat and OpenSMILE toolchain we use.

What none of those are is a deployed, crew-facing tool. Axiom's is a study that
reports to investigators and requires dedicated hardware. Bridge2AI is
cross-sectional and supervised, built to classify which condition a voice
indicates, with mostly one session per participant, so it structurally cannot
train a per-person baseline. Our contribution is the thing that runs on the
laptop the crew already has, needs no labels, no training and no network, and
reports to the person who made the recording.

**Additional data-quality findings from OSD-575.** Beyond the glucose artifact,
running our detector surfaced three more problems in the dataset worth
documenting: a header that breaks its own naming convention (`alt_max` and
`ast_max` where every other analyte uses `_range_max`), which silently drops two
analytes from any code matching the pattern; haptoglobin pinned at 17,907,000 in
seven of twenty-eight samples in the cytokine panel, which is an assay ceiling
rather than a measurement; and reference ranges that shift mid-study for one
subject alone, meaning her pre-flight and post-flight values are not judged
against the same yardstick. Each is reproducible from the committed code.

**What we have not shown.** We have not demonstrated that unexplained drift
predicts anything. NASA's HERA Standard Measures, which hold crew affect scores
from the same isolation analog, is the dataset that would confirm or refute it.
Our thresholds are placeholders that need calibrating against real
session-to-session variability, for which NIH's Bridge2AI-Voice is the right
corpus. Both require credentialed access.

---

## NASA Data & Resources

| Link Text | Link URL |
|---|---|
| NASA Open Science Data Repository, OSD-575 (Inspiration4 serum panel) | https://osdr.nasa.gov/bio/repo/data/studies/OSD-575 |
| OSD-575 file listing (API) | https://osdr.nasa.gov/osdr/data/osd/files/575 |
| Machine Learning for Predicting Team Functioning in HERA Missions (NASA NTRS) | https://ntrs.nasa.gov/citations/20260002431 |
| Predicting Team Functioning in Long Term Space Missions Using Acoustic and Linguistic Measures (NASA NTRS) | https://ntrs.nasa.gov/citations/20260005849 |
| NASA Medical Operations requirements (private medical conferences) | https://www.nasa.gov/reference/6-0-medical-operations/ |
| NASA Human Research Program, Standard Measures at HERA | https://nlsp.nasa.gov/explore/home/lsda_sm_hera |

| 5 Hazards of Human Spaceflight (NASA Human Research Program) | https://www.nasa.gov/hrp/hazards/ |
| Risks of Human Spaceflight (NASA Human Research Program) | https://www.nasa.gov/hrp/risks/ |

---

## Space Agency Partner & Other Data

| Link Text | Link URL |
|---|---|
| Praat (Boersma & Weenink), via the parselmouth Python library | https://parselmouth.readthedocs.io |
| python-soundfile | https://python-soundfile.readthedocs.io |
| FastAPI (local web server for the crew-facing app) | https://fastapi.tiangolo.com |
| SOMVOICE sleep-deprivation speech study (Martin et al., LREC 2026) | https://aclanthology.org/2026.lrec-1.438/ |
| Ollama (optional local language model runtime) | https://ollama.com |
| Safe Passage: Astronaut Care for Exploration Missions, National Academies | https://www.nationalacademies.org/read/10218/chapter/8 |
| FAA field study, cepstrum speech analysis for fatigue in cabin crew | https://rosap.ntl.bts.gov/view/dot/26637 |
| Vocal Markers in Aviation of Workload, Stress, Fatigue and Sleepiness | https://openaccess.cms-conferences.org/publications/book/978-1-964867-65-6/article/978-1-964867-65-6_19 |
| Detecting fatigue in multiple sclerosis through automatic speech analysis | https://pmc.ncbi.nlm.nih.gov/articles/PMC11427396 |
| Spaceflight-Associated Changes in Paranasal Sinus Opacification (JAMA Oto) | https://pmc.ncbi.nlm.nih.gov/articles/PMC7099529 |
| Sinonasal symptoms in 71 ISS astronauts (NASA LSAH retrospective) | https://digitalcommons.library.tmc.edu/baylor_docs/4454 |
| Effects of Body Posture on Voice Range Profile Performance | https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12456106/ |
| NIH Bridge2AI-Voice (related work, not used; cited as calibration path) | https://physionet.org/content/b2ai-voice/ |

---

## Use of Super Intelligence (SI)

Select the options covering code generation and text generation. See the AI
disclosure section of README.md, which judges can see.

---

## Project Links

**Project:** https://github.com/acmross/baseline-drift

**Project Demonstration:** https://acmross.github.io/baseline-drift/pitch-deck.html
Seven slides, public, no password or sign-in. Verified in a fresh browser
profile on 2026-11-15; arrow keys, clicks and the `#2`-`#7` hash move between
slides.

---

## Before submitting

- [ ] Both links open in a private browser window with no sign-in
- [ ] Demo is 7 slides or under 30 seconds, not more
- [ ] NASA data field filled, since Global Award eligibility requires it
- [ ] SI question answered
- [ ] Both verification checkboxes ticked
- [ ] Clicked Submit for Judging, not just Save Progress
