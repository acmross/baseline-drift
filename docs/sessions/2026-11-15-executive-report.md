# Executive report — 2026-11-15

**Bottom line:** Baseline Drift's live surface was verified end to end, the last
known pipeline bug was fixed, the hosted demo's privacy boundaries are now
covered by tests, and the Windows release was rebuilt from `main`. The suite is
92 passing tests, every public link responds, and the repository is clean and
pushed. Submission itself was parked; the team owns the form.

## What shipped

1. **Live verification pass** — one Playwright run, 25 checks across the online
   preview, the seven-slide deck, the hosted demo and the local app.
2. **Detector fix** — `pipeline/voice_drift.analyse` returned a nested tuple when
   nothing moved. It now returns a flat `(stats, [])`; the workaround in
   `web/reporting.py` is gone; `web/tests/test_pipeline.py` pins the contract.
3. **Hosted-demo tests** — `web/tests/test_hosted.py` covers per-visitor
   isolation, the hardened cookie, malformed cookies, the retention sweep, the
   visitor cap, cross-origin health and local mode.
4. **Release refresh** — the exe was rebuilt from `main` and the
   `v0.1-demo-2026-11-14` asset replaced (48,363,233 bytes, sha256
   `6c350cef…`); the download now matches the current UI.
5. **Presentation fixes** — inline favicon on the app and wake page, `docs/try`
   rebuilt, README links the deck.
6. **Handoff corrected** — `docs/INSTRUCTIONS.md`, the 2026-11-14 debrief and
   `NEXT-SESSION.md` now describe the merged, 92-test state.

## Results and evidence

- `python -m pytest web/tests -q` → **92 passed**, one known third-party warning.
- Hosted pipeline, with synthetic audio through the public server: three uploads
  returned 201 with all eight features, the report reached `baseline` at three
  sessions, session detail listed all three takes, audio playback returned
  192 KB, deleting one session removed its three WAVs, and the visitor space
  returned to `empty`.
- Online preview: sample report and trends render, the real four-session dataset
  loads, sessions open, delete asks first, **zero third-party requests**.
- Deck: exactly seven slides; slides 3 and 6 render; hash and arrow navigation
  work; live URL returns 200.
- Local app and packaged exe: offline privacy copy, sample report and trends
  render, **zero external requests**; the exe now serves the favicon.
- Live preview and wake page log **zero console errors** after the favicon fix.
- Repository: `main` at the report commit, worktree clean, `web-ui` worktree
  fast-forwarded.

## Findings and risks

- **Real data is four sessions, not six.** The published real dataset is Amanda's
  four recorded check-ins and reports `stable`. The six-session "two unexplained
  changes" story is the **synthetic fixture**; it must be labelled as such.
- **The microphone path is still manual.** Automation proved the API and the
  rendered UI, not `MediaRecorder`: mic permission, level meter, a live take and
  an upload from the browser still need a human on the demo laptop.
- **`MIN_CHANGE` is still placeholder-calibrated.** It needs repeated
  same-sitting recordings and a separate reviewed change; do not tune it to make
  a demo fire.
- **The deck has no app screenshots** and loads Google Fonts (falls back to
  system fonts offline). It is accurate but text-only.
- **The release tag is dated 2026-11-14** while the asset was rebuilt on
  2026-11-15. The tag name is now slightly misleading; the contents are current.
- **`pipeline/` is nominally read-only.** The detector fix was made as its own
  reviewed commit with tests, as the instructions require.

## Decisions needed

- Who submits the Space Apps form, and whether the seven-slide deck is the
  accepted demonstration link. Recommendation: yes; the hosted demo stays a
  bonus link.
- Whether to run one real microphone take on the demo laptop before submitting.
- Whether to calibrate thresholds now or leave the placeholders and say so.

## Next steps

1. Submit from `SUBMISSION.md` with the deck URL, in a private window.
2. Record one real take through the browser to close the last manual gap.
3. Calibrate `MIN_CHANGE` from repeated real recordings when time allows.
4. Optional: refresh the release notes/tag naming so the date matches the build.

## Artifacts

- Preview: <https://acmross.github.io/baseline-drift/try/>
- Hosted demo: <https://baseline-drift.onrender.com> (wake page at `/demo/`)
- Deck: <https://acmross.github.io/baseline-drift/pitch-deck.html>
- Release: <https://github.com/acmross/baseline-drift/releases/tag/v0.1-demo-2026-11-14>
- Handoff: `NEXT-SESSION.md`, `docs/INSTRUCTIONS.md`, `SUBMISSION.md`
- Verification screenshots: local temp `bd-verify-d70a3rat` (not committed)
