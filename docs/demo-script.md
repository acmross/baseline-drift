# Baseline Drift demo script (2 minutes)

**Setup:** local server running at `http://127.0.0.1:8765`; six synthetic sessions seeded with
`python web/demo_dry_run.py --reset --capture`. The live report is served by the same API the UI uses;
nothing is staged in the page.

**Before you start:** say clearly that the six seeded sessions are synthetic, recorded to prove the
pipeline and demo path. Real crew recordings replace them for the final demo.

---

**0:00 — The problem.**
On a Mars transit, mission control is twenty minutes away and sometimes unreachable. Crews have to spot
changes in themselves, and self-report suffers from survey fatigue and real incentives not to disclose.
We turn a signal crews already produce, their voice, into something they can act on privately.

**0:15 — Baseline state.**
Show the report after three sessions. It says the baseline is complete and scoring begins with the next
session. No findings are claimed yet; the first three sessions are the reference, not a result.

**0:30 — Findings.**
After six sessions the report leads with two changes without a reported explanation: **more pausing** and
**speaking slower**. Show the sparklines against the shaded baseline band and the flagged points.

**0:50 — The split that matters.**
The crew member reported a cold that day. Pitch, voice clarity and loudness are tagged "accounted for:
cold or congestion." Pausing and speaking rate are not, and a cold does not account for them. That
residual is the product: self-report and acoustics each cover the other's blind spot.

**1:10 — Why the method is credible.**
Run the same deviation logic on OSD-575, the Inspiration4 metabolic panel. A z-score alone flagged 65 of
272 comparisons, a quarter, which is noise from a three-sample baseline. Adding a second gate cut it to
11 flags that look real. On synthetic voice control data, two gates still fired once; adding the
persistence gate silenced the control while true drift still fired. Show the progression table.

**1:30 — The honesty beat.**
We do not diagnose fatigue, stress or mood. Every line is a measurement plus a duration. We compare you
to you and leave interpretation to the crew member. If the tired-day session does not fire, we report
that null result too.

**1:50 — What is next.**
The sensor layer as a second input stream, and validation against reaction-time testing. The crew-facing,
offline framing is the novelty: existing work predicts crew state for mission control; this reports to
the crew member.

---

## Backup plan

- **Mic fails:** keep the seeded report open. It is the real UI reading the real API; only the audio is
  synthetic, and you say so.
- **Server fails:** `docs/demo/report-findings.png` and `docs/demo/report-baseline.png` are the captured
  states. The static report from `pipeline/make_report.py` is the second fallback.
- **Judge asks why the audio sounds like a buzz:** because it is a test fixture, not speech. Real
  recordings are the demo data; the buzz proves the path.

## Judge questions

The prepared answers are in `GroundState.PRD.md` §10: mood, accents/colds,
data required, and novelty. Keep the 80–91% HERA figure tied to team cohesion and efficacy, never to
individual fatigue detection.
