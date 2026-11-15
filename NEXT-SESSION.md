# Next session

**Single outcome:** a submitted, demo-ready Baseline Drift entry with real recordings, verified links, and the PR merged.

**Where:** work in `D:\Ruben\2026.Nasa.Hackathon\.worktrees\web-ui` (branch `web-ui`, PR #1) until the merge. Read `docs/INSTRUCTIONS.md` first.

---

## P0 — before anything else

- [ ] Run the full suite: `python -m pytest web/tests -v` → 65 passed.
- [ ] Open PR #1 and read the review comments. Address any actionable feedback before new work.
- [ ] Confirm the local event and its timezone; the submission deadline follows it (Sunday, Nov 15, 11:59 PM local).
- [ ] Confirm the submission form fields and the SI/AI declaration requirements.

## P0 — real recordings and browser checks

- [ ] On the demo laptop, one microphone, one room: record six sessions (days 1-6) through the real UI.
- [ ] Verify the browser checks that were never automated:
  - mic permission prompt and level meter
  - three takes complete in order, passage text visible during take 2
  - upload lands in `web/data/recordings/<SUBJECT>/`
  - keyboard-only flow, focus states, contrast
  - network disabled: page loads and the report still works
  - no external requests in the browser network panel
- [ ] Day 3: report says baseline complete and scoring begins next session.
- [ ] Day 6: report shows sustained findings. On the demo day, report a real cold with normal sleep and unchanged setup; confirm pitch/clarity/loudness are explained and pausing/rate remain unexplained.
- [ ] If the genuine tired-day session does not fire, keep the null result and say so. Do not hand-tune thresholds to force it.

## P0 — calibration

- [ ] Record the same passage several times in one sitting; measure the spread of each feature.
- [ ] Set `MIN_CHANGE` in `pipeline/voice_drift.py` above the measured noise floor. This is a pipeline change; review it separately and keep the tests green.
- [ ] Re-run the six-session report and the e2e test after calibration. Record the thresholds in the demo notes.

## P0 — demo and deck

- [ ] Refresh the 7-slide deck using `docs/demo/record.png`, `docs/demo/report-baseline.png`, and `docs/demo/report-findings.png`.
- [ ] Use the 2-minute walkthrough in `docs/demo-script.md` as the spoken track.
- [ ] Keep the 80-91% HERA figure tied to team cohesion/efficacy, never individual fatigue.
- [ ] Both submission links public, no password, no sign-in. Test them in a private browser window.
- [ ] Include the OSD-575 citation and the caveats; declare AI tools honestly.

## P1 — merge and package

- [ ] Merge PR #1 into `main` after the P0 checks.
- [ ] Rebuild the exe from merged `main`: `.\build_exe.ps1`, then smoke-test `dist\BaselineDrift.exe`.
- [ ] Optional: publish a GitHub release and attach the exe as a release asset (do not commit the 48 MB binary).
- [ ] Push `main`; leave the worktree clean.

## P1 — optional improvements (only if time remains)

- [ ] Fix the `pipeline/voice_drift.analyse` empty-return precedence bug upstream and remove the workaround in `web/reporting.py`; add a stable-state test.
- [ ] Add TestClient coverage for `/api/questions`, `/api/context`, and `/api/report`.
- [ ] Strengthen the offline audit to catch protocol-relative URLs and CSS `url(https://…)`.
- [ ] Add try/catch and retry paths for report loading if the demo network stack proves flaky.
- [ ] Add contract docstrings to the two remaining route handlers.

## Definition of done

- [ ] 65+ tests pass on the merged tree.
- [ ] Six real sessions produce the expected baseline and findings states.
- [ ] Exe builds from merged `main` and serves the UI at 127.0.0.1.
- [ ] Both submission links open in a private window.
- [ ] Submission clicked before the deadline, with buffer.

## Risks

| Risk | Mitigation |
| --- | --- |
| Real voice does not move enough to clear `MIN_CHANGE` | Calibrate above the noise floor; report the null if it still does not fire. |
| Browser audio or mic fails on the demo laptop | Test early; fall back to the synthetic dry-run report and say it is synthetic. |
| PR merge is delayed | Submit from the branch if necessary; merge after. |
| Deadline/timezone confusion | Confirm the local event and submit with at least one hour of buffer. |
| Missing AI/data declaration | Prepare it before the final hour; do not retrofit at 11 PM. |
