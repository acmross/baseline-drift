# Session debrief — 2026-11-14

> **Update 2026-11-15:** PRs #1–#9 are merged, so `main` is the working branch.
> The suite is now 92 tests. The online preview, hosted demo and seven-slide deck
> are live, and the release exe was rebuilt from `main`. The text below is the
> record of the 2026-11-14 session; where it says the PR is unmerged or the
> suite has 65 tests, this update overrides it.

**Bottom line:** Baseline Drift is a working, reviewed, offline voice check-in app with a winning PRD, a passing test suite, a synthetic demo capture, and a Windows executable. The work is on branch `web-ui` in PR #1 and is not yet merged. Real recordings and the final submission remain.

## What shipped

1. **Winning PRD** — `GroundState.PRD.md`, 15 sections: challenge fit, judging strategy, product scope, UX spec, architecture, three-gate validation, data plan, privacy position, demo/pitch, team/timeline, risks, and submission checklist.
2. **Implementation plan** — `docs/superpowers/plans/2026-11-14-baseline-drift-web-ui.md`, 10 TDD tasks with exact files, interfaces, tests, and code.
3. **Web UI** — one offline page with Record (vowel, passage, free speech, countdown, level meter, WAV encoding, retry), Check-in (six skippable questions, raw text parsed server-side with CLI parity), and Report (unexplained-first findings, sparklines against the baseline band, stable list, descriptive-only copy).
4. **Local API** — FastAPI on `127.0.0.1:8765`: health, session upload, questions, context, report JSON. No external requests.
5. **Tests** — 65 passing, including an end-to-end six-session path.
6. **Demo capture** — `docs/demo/record.png`, `report-baseline.png`, `report-findings.png`; walkthrough in `docs/demo-script.md`; reproducible seed in `web/demo_dry_run.py`.
7. **Windows exe** — `dist\BaselineDrift.exe` (48.3 MB), built with PyInstaller; starts the server, opens the browser, writes data beside the exe.
8. **Session handoff** — `docs/INSTRUCTIONS.md`, `NEXT-SESSION.md`, this debrief.

## Results and evidence

- Full suite: **65 passed, 1 pre-existing warning** (`python -m pytest web/tests -v`).
- Synthetic demo through the live API:
  - Baseline (3 sessions): "Baseline complete — scoring begins with your next session."
  - Findings (6 sessions + day-6 cold check-in): "2 changes without a reported explanation."
  - Unexplained: pausing, speaking rate. Explained by the reported cold: pitch, voice clarity, loudness.
- Exe smoke test: health OK, UI title "Baseline Drift", report headline and 5 rows rendered, **zero external requests**.
- Final whole-branch review found 2 Critical and 5 Important issues; all were fixed in `056b409` and passed a scoped re-review:
  - fixed passage now shown during take 2, with countdown and 45s take
  - raw check-in text parsed server-side with CLI parity and `_raw` storage
  - exactly three sessions reports baseline, not stable
  - failure recovery and retry paths
  - button/input contrast
  - browser audio processing disabled by request
  - stable features rendered

## Findings and risks

- **Synthetic, not speech.** The demo audio is a source-model buzz. It proves wiring and report states, not acoustic validity. Real recordings are still required.
- **Browser checks were not executed.** Mic permission, real takes, keyboard walk, contrast, and the six-session live run remain manual. The e2e test proves the API path, not MediaRecorder.
- **`MIN_CHANGE` is still placeholder-calibrated.** Set thresholds from repeated same-sitting recordings before trusting real output.
- **Pipeline bug worked around, not fixed.** `pipeline/voice_drift.analyse` returns `(stats, (stats, []))` on empty findings; `web/reporting.py` normalizes it because the pipeline was read-only. The CLI stable case is still affected.
- **PR not merged.** All work is on `web-ui`. The exe is gitignored and must be rebuilt from merged source.
- **Main advanced during the session.** The teammate added `SUBMISSION.md` and replaced `docs/pitch.md` (`e25fe30`); session docs were rebased on top (`eb3d841`). The `web-ui` branch was then merged with `main` (`518a0b0`) and the `.gitignore` conflict resolved. GitHub reported PR #1 **MERGEABLE/CLEAN** at close (head `518a0b0`, base `9b55137`, main ahead at `2e1cef5`).
- **Submission clock.** November 15, 11:59 PM local event time (San Jose); saving is not submitting. Form copy is drafted in `SUBMISSION.md`; public links, OSD-575 citation, and the SI declaration still need to be verified and submitted.

## Decisions made

- Challenge #5, Create Health Monitoring Software for Astronauts, with the voice-first approach.
- Crew-facing, offline, per-person baseline; no diagnosis or mood claims.
- Worktree + PR instead of working on `main`.
- No watchdog timer for this project, per the session instruction.
- Synthetic dry run for the demo path; real recordings for the final demo.
- Exe as a convenience artifact, not committed to the repository.

## Next steps

Follow `NEXT-SESSION.md`. The short version: real six-session recording, browser manual checks, `MIN_CHANGE` calibration, deck refresh, merge PR #1, rebuild the exe, verify public links, submit with buffer.

## Artifacts

- PR: https://github.com/acmross/baseline-drift/pull/1 (head `518a0b0`; base `main`)
- Main head at session close: latest `main` with the handoff docs
- Submission form copy: `SUBMISSION.md`
- Branch head at session close: `518a0b0`
- Worktree: `D:\Ruben\2026.Nasa.Hackathon\.worktrees\web-ui`
- Exe: `D:\Ruben\2026.Nasa.Hackathon\.worktrees\web-ui\dist\BaselineDrift.exe`
- Release: https://github.com/acmross/baseline-drift/releases/tag/v0.1-demo-2026-11-14 (`BaselineDrift.exe`, 48.3 MB)
- Execution ledger: `.worktrees\web-ui\.superpowers\sdd\2026-11-14-baseline-drift-web-ui\progress.md`
