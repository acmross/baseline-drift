# Instructions: run, test, demo, and continue Baseline Drift

This file is the operating manual for the next session. Read it before touching code.

## Where the work lives

- Main checkout: `D:\Ruben\2026.Nasa.Hackathon` (branch `main`).
- Implementation branch: `web-ui` in the worktree `D:\Ruben\2026.Nasa.Hackathon\.worktrees\web-ui`.
- Pull request: https://github.com/acmross/baseline-drift/pull/1
- Submission form copy: `SUBMISSION.md` (San Jose event).
- `main` advanced during the session with the teammate's submission/pitch commits (`e25fe30`); session docs were rebased on top (`eb3d841`). The PR branch head is `518a0b0` after merging `main` into it.
- Do the next work in the worktree while the PR is open. Merge the PR only after the manual browser checks and real recordings are done.

## Run the app from source

```powershell
cd D:\Ruben\2026.Nasa.Hackathon\.worktrees\web-ui
python -m pip install -r web/requirements.txt
python -m uvicorn web.server:app --host 127.0.0.1 --port 8765
```

Open http://127.0.0.1:8765. One page, three states: Record, Check-in, Report.

Data is written under `web/data/` (gitignored):
- `web/data/recordings/<SUBJECT>/<day>_{vowel,passage,free}.wav`
- `web/data/sessions.jsonl`
- `web/data/context.jsonl`

## Tests

```powershell
python -m pytest web/tests -v
```

Expected: 65 passed, 1 known third-party warning. Do not weaken tests to make them pass.

## Demo dry run (synthetic)

With the server running:

```powershell
python web/demo_dry_run.py --reset --capture
```

This seeds three baseline and three drifting sessions, stores a day-6 cold check-in, prints the report summary, and writes:
- `docs/demo/record.png`
- `docs/demo/report-baseline.png`
- `docs/demo/report-findings.png`

The audio is a source-model buzz, not speech. Say so when presenting it; it proves wiring, not acoustic validity.

## Real demo sequence

1. Use one laptop, one microphone, one room for every session.
2. Record days 1-6 with the same three takes: sustained "ah", the fixed passage, free speech.
3. Day 3 completes the baseline; the report says scoring begins next session.
4. Day 4 is the first scored session; the persistence gate means the earliest finding is day 5.
5. On the demo day, report a real cold in the check-in but normal sleep and an unchanged setup. The report should explain pitch, clarity and loudness, and leave pausing and speaking rate unexplained.
6. If the tired-day session does not fire, report the null result. That is a real result.

Browser-only checks that still need a human:
- Microphone permission prompt, level meter, three takes, upload.
- No external requests with the network disabled.
- Keyboard walk, contrast, and focus states.
- Exact six-session report on day 6.

## Build the Windows executable

```powershell
cd D:\Ruben\2026.Nasa.Hackathon\.worktrees\web-ui
.\build_exe.ps1
.\dist\BaselineDrift.exe
```

- Single-file exe, about 48 MB, starts `127.0.0.1:8765`, opens the browser.
- Data goes to `data\` beside the exe. Override with `BASELINE_DRIFT_DATA`.
- `BASELINE_DRIFT_NO_BROWSER=1` is for automated smoke tests.
- The exe is gitignored; rebuild it from source rather than committing it.

## Hard constraints (do not break)

- No runtime network calls, no external fonts, CDNs, analytics, or telemetry.
- Bind the server to `127.0.0.1` only.
- Descriptive wording only: measurement plus duration. Never "fatigued", "stressed", a diagnosis claim, or "normal range".
- `pipeline/` and `validation/` are read-only. If you must change them, do it in a separate reviewed change.
- One page, three states, no router, no build step, no framework.

## Troubleshooting

- **`parselmouth` install fails:** use a Python 3.12 venv. The 3.14 wheel installed cleanly on this machine; the fallback is documented in the plan.
- **Port 8765 in use:** stop the existing server first. Never start a second dev server.
- **Browser records WebM/Opus:** the UI decodes and re-encodes PCM WAV; do not rename files.
- **"Session already recorded" (409):** the subject/day pair exists. Use a new day or delete the demo data after confirming it is disposable.
- **Tests write real data:** they use temp directories. If `web/data/` appears, it is gitignored.
- **PowerShell here-strings:** use Git Bash at `C:\Program Files\Git\bin\bash.exe` for POSIX scripts; WSL bash is broken on this machine.

## Key files

- `web/server.py` — local API, static serving, frozen-mode data dir.
- `web/reporting.py` — report JSON, baseline/stable/findings states.
- `web/context_builder.py` — raw answers to explains map (CLI parity).
- `web/app/` — one-page UI.
- `web/demo_dry_run.py` — synthetic demo and screenshots.
- `web/tests/` — 65 tests.
- `baseline_drift_exe.py`, `build_exe.ps1` — packaged launcher and build.
- `GroundState.PRD.md` — winning PRD.
- `docs/superpowers/plans/2026-11-14-baseline-drift-web-ui.md` — implementation plan and task history.
- `.worktrees\web-ui\.superpowers\sdd\2026-11-14-baseline-drift-web-ui\progress.md` — execution ledger.
