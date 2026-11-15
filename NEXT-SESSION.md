# Next session — Sunday 15 November 2026 (submission day)

**Single outcome:** Baseline Drift is submitted for judging before 23:59 Pacific,
with every required field filled and every public link opened in a private window.

**Where:** `D:\Ruben\2026.Nasa.Hackathon` (branch `main`, clean and pushed). The
`web-ui` worktree tracks the same commit; PRs #1–#9 are merged. Read
`docs/INSTRUCTIONS.md` for how to run the app; the form copy lives in
`SUBMISSION.md`. The session record is
`docs/sessions/2026-11-15-executive-report.md`.

## Done today after the verification pass

- Detector: `pipeline/voice_drift.analyse` returns a flat `(stats, [])` when
  nothing moved; the reporting workaround is gone; `web/tests/test_pipeline.py`
  pins the shape and the CLI stable case no longer crashes.
- Hosted demo: `web/tests/test_hosted.py` proves per-visitor isolation, the
  hardened cookie, malformed-cookie replacement, the retention sweep, the
  visitor cap, cross-origin health and local mode (7 tests).
- Exe rebuilt from `main` and the `v0.1-demo-2026-11-14` asset replaced; the
  smoke test passed with no external requests.
- Favicon on the app and the wake page, `docs/try` rebuilt; the console
  `favicon.ico` 404s are gone.
- `docs/INSTRUCTIONS.md` and the 2026-11-14 debrief corrected; README links the
  deck.
- Suite: **92 passed**.

---

## State verified at 14:45 Pacific

- Full suite: **92 passed** on `main` (`python -m pytest web/tests -q`).
- Online preview: <https://acmross.github.io/baseline-drift/try/> → 200.
- Hosted demo wake page: <https://acmross.github.io/baseline-drift/demo/> → 200.
- Hosted demo health: <https://baseline-drift.onrender.com/api/health> → `{"ok":true}`.
- Seven-slide deck: <https://acmross.github.io/baseline-drift/pitch-deck.html> → 200,
  7 slide sections, renders in a fresh Chrome profile, `1/7` pager visible.
- Published real dataset: 4 sessions (`day5`, `day7`, `fd8`, `fd9`), state `stable`.
  It is the team member's real data from her laptop, check-in answers excluded.
- The six-session findings story (2 unexplained: pausing, speaking rate; 3 explained
  by the reported cold: pitch, voice clarity, loudness) comes from the **synthetic**
  fixture. Say that out loud if you present it.
- The `v0.1-demo-2026-11-14` release exe was built 2026-11-14 23:06, before the
  tabs, session playback, deletion and hosted demo landed. It is stale but usable.

## Live browser verification (fresh Chrome profile, 14:40–14:45)

One Playwright pass: **25 checks passed**, 2 console errors, both only
`favicon.ico` 404s (cosmetic).

- **Preview** — sample report and 36-session trends render (8 measure rows); the
  dataset switch loads the real four-session report; a session opens with its
  measurements and "not published" notes; Delete raises the confirm dialog;
  **zero third-party requests**.
- **Deck** — 7 slides, `1/7` pager, slides 3 and 6 render correctly, `#2`–`#7`
  hashes and arrow keys navigate.
- **Hosted demo** — the wake page redirects to Render; the banner says everything
  is deleted within 2 hours; three synthetic uploads produced **201** with all
  eight features; the report reached `baseline` at 3 sessions; session detail
  listed all three takes; audio returned 192 KB; deleting one session removed
  its 3 audio files and the report count dropped to 2; the visitor space was
  cleaned back to `empty`.
- **Local app** — offline privacy copy, sample report and trends render;
  **zero external requests**.

**Not covered by automation:** the microphone and MediaRecorder path (permission
prompt, level meter, real takes, upload from the UI), check-in submit through the
browser, keyboard-only walk, focus states and contrast. Those need a human at the
demo laptop.

## Decision needed: how to fill *Project Demonstration*

**Option A — link the existing seven-slide deck (recommended).**
Pros: already live, exactly 7 slides, public and sign-in-free, verified in a
private profile, no production time, matches the required format literally.
Cons: no app screenshots in it; it loads Google Fonts (falls back to system fonts
offline); the "in our run" line refers to synthetic data unless the presenter
says so.

**Option B — record a 30-second screen video.**
Pros: shows the real UI and the report states, which judges remember.
Cons: a new recording, upload, public link and private-window check; 30 seconds
cannot carry the three-gate argument; loses the before/after view a judge can
sit on. High effort, new failure points, low marginal gain.

**Option C — use the hosted demo URL as the demonstration link.**
Pros: a judge can run the real pipeline immediately.
Cons: the field asks for slides or a video; a live app is not that format; the
free Render instance can sleep for up to a minute, adding friction on first
load. Better kept as a bonus in the project details, where the README already
links it.

**Recommendation:** Option A now, Option C only as an extra link in the written
details. Do not start Option B today.

## P0 — submit (parked this session; the team owns the form)

- [x] Automated live pass (above): preview, deck, hosted pipeline, local app.
      The "verify first" step chosen for today is done; only the mic path needs a
      human.
- [ ] If a human is at the demo laptop, run one real take through the browser and
      confirm the level meter, the three takes and the upload. Otherwise say the
      hosted API path was verified with synthetic audio and move on.
- [ ] Confirm who is clicking Submit and that they are signed in to the team's
      Space Apps account. Everything below is worthless until that is settled.
- [ ] Confirm the deadline in the event's own timezone (San Jose, 23:59 Pacific).
- [ ] Paste the blocks from `SUBMISSION.md`: Summary, Project Details, NASA Data,
      Space Agency Partner, Super Intelligence declaration, Project Links.
      The demonstration link is the deck URL; the project link is the GitHub repo.
- [ ] NASA Data field: OSD-575, HERA NTRS citations, NASA medical operations,
      HERA Standard Measures, 5 Hazards and Risks of Human Spaceflight.
- [ ] SI declaration: code generation and text generation, per the README's
      "Use of AI tools" section.
- [ ] Private-window check: repository, deck, online preview, hosted demo.
      Confirm no password, no sign-in, and that the deck shows 7 slides.
- [ ] Tick both verification checkboxes and click **Submit for Judging**, not
      Save Progress. Screenshot the confirmation.
- [ ] Record the submission time and any confirmation URL at the bottom of
      `SUBMISSION.md`.

## P1 — done on 2026-11-15, independent of the submission

- [x] Rebuilt the exe from `main`, smoke-tested it, and replaced the
      `v0.1-demo-2026-11-14` asset (48,363,233 bytes; sha256
      `6c350cef…`). The release download now matches the current UI.
- [x] Added the deck link to the README's "Try it" section.
- [x] Corrected `docs/INSTRUCTIONS.md` and added a dated update to the
      2026-11-14 debrief.
- [x] Added an inline favicon to the app and the wake page, rebuilt `docs/try`,
      and confirmed both live pages log zero console errors.

## Do not start today

- Six real sessions. Two more days of real data cannot be fabricated; the
  published four-session real set stays as it is.
- `MIN_CHANGE` calibration. It needs repeated same-sitting recordings and a
  separate reviewed pipeline change. Do not move thresholds to make a demo fire.
- The optional upstream `pipeline/voice_drift.analyse` fix and extra API tests.

## Risks

| Risk | Mitigation |
| --- | --- |
| Deadline/timezone confusion | Submit with at least two hours of buffer; screenshot the confirmation. |
| Wrong link in the demonstration field | Use the deck URL above; open it in a private window from the form machine. |
| Hosted demo sleeps during judging | The wake page polls and redirects; the deck and preview need no server. |
| The deck's "our run" reads as real speech | Say "synthetic six-session fixture" wherever the result is discussed; the README already labels it. |
| Team member's real data is only 4 sessions | Present it as real recorded use, not as a completed six-session result. |
| Mic path never tested in a browser | Test one take on the demo laptop before submitting; the hosted API path is already proven with synthetic audio. |
