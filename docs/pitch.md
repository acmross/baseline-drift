# Baseline Drift

**Team Ground State. NASA Space Apps 2026, Create Health Monitoring Software
for Astronauts.**

## In one paragraph

Astronauts on long missions carry most of the responsibility for noticing
changes in their own health, at exactly the distance where help is slowest.
Baseline Drift is a daily voice check-in that runs offline on the crew's own
laptop. It extracts eight acoustic features, compares them against that
person's own earlier sessions rather than a population norm, and reports what
moved, how far, and for how long. It never says why.

## The problem

NASA flight surgeons hold a private medical conference with each ISS crew
member weekly. At Mars distance that conversation stops being real time,
exactly as the need for it grows. Self-report is the fallback, and it is a weak
instrument: the National Academies has documented that astronauts face real
pressure to withhold medical information, because anything disclosed may affect
whether they fly again.

## Why voice

Crews already record daily audio logs, so the signal costs nothing to collect.
NASA-funded work on the HERA isolation analog predicted crew efficacy and
cohesion at 80 to 91 percent from acoustic features alone. Axiom's Voice in
Space is flying a related study now. The signal is real and others are
measuring it. What nobody has deployed is the version that runs on the crew's
own machine and reports to them.

## How it works

Three gates, each added because the previous set let noise through.

1. A z-score of at least 2.0 against this speaker's own baseline.
2. A change exceeding a minimum meaningful size in the feature's own units.
3. The same feature moving the same direction across consecutive sessions.

A short check-in runs alongside: congestion, cough, sleep, posture, setup
changes. Each answer declares which features it could plausibly account for. A
reported cold licenses voice quality. A headache licenses nothing, because it
has no established acoustic signature.

## The result that matters

We validated the method on NASA OSD-575, the Inspiration4 serum panel, before
applying it to voice. A z-score alone flagged 65 of 272 comparisons. Adding a
reference-range gate cut it to 11.

Among the survivors: glucose below range in three of four crew at R+45. Forty
five days after landing, that is sample handling or fasting status, not
spaceflight. Our detector fired correctly and the cause was logistics. A tool
that had named a cause would have been confidently wrong.

## The design position

Two channels that fail in opposite directions. Self-report fails when someone
will not say. Acoustics fail when something benign moves the numbers. Neither
is trustworthy alone, and the design does not depend on candour: concealing a
cold pushes the drift into the unexplained column, which is the one the report
highlights. It fails safe.

Nothing leaves the habitat. NASA already runs the ground channel. We build what
the crew member brings to it.

## What we have not shown

That unexplained drift predicts anything. HERA Standard Measures is the dataset
that would settle it. Our thresholds are placeholders needing calibration
against real session-to-session variability, for which Bridge2AI-Voice is the
right corpus. Both require credentialed access.
