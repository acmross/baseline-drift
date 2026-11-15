# Baseline Drift Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the crew-facing one-page Record → Check-in → Report experience, wired to the existing offline voice-drift pipeline, with tests and a demo-ready synthetic dry run.

**Architecture:** A local FastAPI app in `web/server.py` serves one static page from `web/app/` and exposes local JSON/multipart endpoints. The browser captures three takes, decodes them to PCM, encodes WAV, and posts them; the server validates WAV, extracts per-task features with `pipeline/voice_features.py`, merges them into one session record, appends JSONL under `web/data/`, and serves analysis JSON built on `pipeline/voice_drift.py`.

**Tech Stack:** Python 3.14 (fallback 3.12 venv), FastAPI, Uvicorn, pytest, httpx TestClient, NumPy, praat-parselmouth, soundfile, vanilla HTML/CSS/JS (no build step, no CDN).

## Global Constraints

- No network calls at runtime: no external fonts, CDNs, analytics, or telemetry. A static audit test enforces this.
- Bind the server to `127.0.0.1` only; never `0.0.0.0`.
- Descriptive language only: every user-visible finding is a measurement plus a duration; never "fatigued", "stressed", "diagnosis", or "normal range".
- Use "your baseline" wording; never "normal".
- One page, three states; no router, no build step, no framework.
- Must work with `--backend none`: no Ollama, no model required.
- Data stays local under `web/data/`; recordings and JSONL are gitignored.
- Existing `pipeline/` and `validation/` files are read-only unless a task explicitly says otherwise.
- Tests run with `python -m pytest web/tests -v` from the repo root and must be green before each commit.

## File Structure

```
web/
  server.py              FastAPI app factory + endpoints
  requirements.txt       runtime + test dependencies
  session_store.py       JSONL append/read, ID validation, duplicate detection
  feature_merge.py       three take feature dicts -> one session feature dict
  context_builder.py     structured answers -> explains map
  reporting.py           records + context -> report JSON for the UI
  app/
    index.html           one page, three sections
    styles.css           design tokens + layout
    app.js               state machine, capture, WAV encode, render
  tests/
    conftest.py          sys.path, temp data dir, WAV fixture
    test_static.py       health, static serving, offline audit
    test_store.py        ID validation, JSONL, duplicates
    test_merge.py        per-task feature sourcing, null handling
    test_upload.py       WAV validation, upload limits, duplicate rejection
    test_context.py      explains parity with checkin_agent rules
    test_report.py       report JSON states and ordering
    test_ui_contract.py  required IDs, no external assets, no diagnostic copy
    test_e2e.py          six synthetic sessions -> findings report
  README.md              run instructions + demo checklist
  data/                  gitignored runtime data
```

## Luck Moves

These are cheap, reversible probes run before committing to the risky paths. They exist because each one can invalidate a plan assumption in minutes instead of hours.

| Risk | Probe (5 minutes) | Fallback if it fails |
| --- | --- | --- |
| praat-parselmouth has no Python 3.14 wheel | `python -m pip install praat-parselmouth soundfile` and import both | Create a 3.12 venv: `py -3.12 -m venv .venv` then install there; run all tests with `.venv\Scripts\python` |
| Browser WebM/Opus cannot be decoded to WAV in the demo browser | Open a scratch page, record 5 seconds, run `decodeAudioData`, inspect sample rate and channel count | Capture raw PCM with an `AudioWorklet` and write the WAV header directly |
| FastAPI multipart upload rejects real WAVs | Post one real recording to `/api/session` on day one | Send base64 JSON and decode server-side |
| Demo runs out of time before the UI is finished | Render `report.html` from `pipeline/make_report.py` on pre-recorded sessions | Demo the static report and the API; keep the one-page UI as the walkthrough |

Three untried avenues if a step stalls twice: inspect the pipeline's existing example JSONL, reuse `make_report.build()` for a static fallback, and ask the local event's mentors whether their laptop browser differs.

---

### Task 1: Preflight environment and repo hygiene

**Files:**
- Create: `web/requirements.txt`
- Modify: `.gitignore`

**Interfaces:**
- Produces: a working Python interpreter with `parselmouth`, `soundfile`, `pytest`, `fastapi`, `uvicorn`, `httpx` importable; `web/data/` and `.venv/` ignored.

- [ ] **Step 1: Install dependencies on the default interpreter**

Run:

```powershell
python -m pip install praat-parselmouth soundfile pytest python-multipart
```

Expected: all install, and `python -c "import parselmouth, soundfile, pytest; print('ok')"` prints `ok`.

If parselmouth fails to build on 3.14, run the fallback and use `.venv\Scripts\python` for every later command:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install praat-parselmouth soundfile pytest fastapi uvicorn httpx numpy python-multipart
```

- [ ] **Step 2: Verify the existing pipeline end to end**

Run from the repo root:

```powershell
python pipeline\make_test_audio.py pipeline\audio
Push-Location pipeline
foreach ($d in "day1","day2","day3","day4","day5","day6") { python voice_features.py CDR-01 $d audio/$d.wav }
python voice_drift.py sessions.jsonl
Pop-Location
```

Expected: the drift report shows multiple features for day4–day6 and none for day1–day3. This is the known-good state to return to if later work stalls.

- [ ] **Step 3: Write `web/requirements.txt`**

```text
fastapi>=0.115
uvicorn>=0.30
httpx>=0.27
pytest>=8
python-multipart>=0.0.9
numpy>=1.26
praat-parselmouth>=0.4.5
soundfile>=0.12
```

- [ ] **Step 4: Extend `.gitignore`**

Append:

```text
web/data/
.venv/
```

- [ ] **Step 5: Commit**

```powershell
git add .gitignore web/requirements.txt
git commit -m "chore: add web dependencies and ignore runtime data"
```

---

### Task 2: Server skeleton, static shell, offline audit

**Files:**
- Create: `web/server.py`
- Create: `web/app/index.html`
- Create: `web/app/app.js`
- Create: `web/app/styles.css`
- Create: `web/tests/conftest.py`
- Create: `web/tests/test_static.py`

**Interfaces:**
- Produces: `create_app(data_dir: Path | None = None, static_dir: Path | None = None) -> FastAPI`; routes `GET /api/health`, `GET /`, `GET /app.js`, `GET /styles.css`.

- [ ] **Step 1: Write the failing tests**

`web/tests/conftest.py`:

```python
"""Shared test setup: import the repo root and isolate runtime data."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
```

`web/tests/test_static.py`:

```python
"""Static shell, health endpoint, and the offline-only audit."""
import re
from pathlib import Path

from fastapi.testclient import TestClient

from web.server import create_app

APP = Path(__file__).resolve().parents[1] / "app"


def client(tmp_path):
    return TestClient(create_app(data_dir=tmp_path / "data", static_dir=APP))


def test_health(tmp_path):
    r = client(tmp_path).get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "offline": True}


def test_index_is_served(tmp_path):
    r = client(tmp_path).get("/")
    assert r.status_code == 200
    assert "Baseline Drift" in r.text


def test_no_external_assets():
    network = re.compile(
        r'(?:src|href)\s*=\s*["\']https?://'
        r'|fetch\(\s*["\']https?://'
        r'|@import\s+(?:url\()?["\']?https?://'
        r'|fonts\.(?:googleapis|gstatic)\.com',
        re.I,
    )
    for name in ("index.html", "app.js", "styles.css"):
        text = (APP / name).read_text(encoding="utf-8")
        assert not network.search(text), name
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest web/tests/test_static.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'web'` or missing `create_app`.

- [ ] **Step 3: Write the minimal server**

`web/server.py`:

```python
"""
Baseline Drift local server.

Serves the one-page crew UI and the pipeline endpoints on 127.0.0.1 only.
No network calls leave this process; the browser page loads no external assets.
"""
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def create_app(data_dir: Path | None = None, static_dir: Path | None = None) -> FastAPI:
    """Build the app. Tests pass temp paths; production uses web/data and web/app."""
    data = Path(data_dir or (Path(__file__).parent / "data"))
    static = Path(static_dir or (Path(__file__).parent / "app"))
    data.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="Baseline Drift", docs_url=None, redoc_url=None)
    app.state.data_dir = data
    app.state.static_dir = static

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "offline": True}

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(static / "index.html", media_type="text/html")

    @app.get("/app.js")
    def app_js() -> FileResponse:
        return FileResponse(static / "app.js", media_type="text/javascript")

    @app.get("/styles.css")
    def styles() -> FileResponse:
        return FileResponse(static / "styles.css", media_type="text/css")

    return app


app = create_app()
```

- [ ] **Step 4: Write the minimal shell**

`web/app/index.html`:

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Baseline Drift</title>
<link rel="stylesheet" href="/styles.css">
</head>
<body>
<main class="wrap">
  <header class="masthead">
    <h1>Baseline Drift</h1>
    <p class="sub">Daily voice check-in · stays on this machine</p>
  </header>
  <section id="record" class="panel" aria-labelledby="record-title">
    <h2 id="record-title">Record</h2>
  </section>
  <section id="checkin" class="panel" hidden aria-labelledby="checkin-title">
    <h2 id="checkin-title">Check-in</h2>
  </section>
  <section id="report" class="panel" hidden aria-labelledby="report-title">
    <h2 id="report-title">Report</h2>
  </section>
  <div id="status" role="status" aria-live="polite"></div>
</main>
<script src="/app.js"></script>
</body>
</html>
```

`web/app/app.js`:

```javascript
"use strict";

const state = { subject: "AMANDA", session: null, takes: {} };

function showState(name) {
  for (const id of ["record", "checkin", "report"]) {
    document.getElementById(id).hidden = id !== name;
  }
}

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}

showState("record");
```

`web/app/styles.css`:

```css
:root {
  --surface-0: #121211;
  --surface-1: #1a1a19;
  --surface-2: #232322;
  --text-primary: #f0efec;
  --text-secondary: #c3c2b7;
  --text-muted: #8a897f;
  --series-1: #3987e5;
  --accent: #d95926;
  --line: #32322f;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 16px;
  --space-4: 24px;
  --space-5: 40px;
  --radius: 6px;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--surface-0); color: var(--text-primary);
  font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
}
.wrap { max-width: 760px; margin: 0 auto; padding: var(--space-5) var(--space-4); }
.masthead { border-bottom: 1px solid var(--line); padding-bottom: var(--space-3); margin-bottom: var(--space-4); }
h1 { font-size: 19px; margin: 0 0 var(--space-1); font-weight: 600; letter-spacing: -0.01em; }
.sub { color: var(--text-muted); font-size: 13px; margin: 0; }
h2 { font-size: 16px; margin: 0 0 var(--space-3); font-weight: 600; }
.panel { background: var(--surface-1); border: 1px solid var(--line); border-radius: var(--radius); padding: var(--space-4); }
#status { margin-top: var(--space-3); color: var(--text-secondary); font-size: 13px; min-height: 1.5em; }
button {
  min-height: 44px; min-width: 44px; padding: 0 var(--space-3);
  background: var(--series-1); color: #fff; border: 0; border-radius: var(--radius);
  font: inherit; cursor: pointer;
}
button.secondary { background: var(--surface-2); color: var(--text-primary); border: 1px solid var(--line); }
button:disabled { opacity: 0.45; cursor: not-allowed; }
button:focus-visible, a:focus-visible { outline: 2px solid var(--text-primary); outline-offset: 2px; }
a { color: var(--series-1); }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest web/tests/test_static.py -v`

Expected: 3 passed.

- [ ] **Step 6: Commit**

```powershell
git add web/server.py web/app web/tests/conftest.py web/tests/test_static.py
git commit -m "feat: add local server shell and offline audit"
```

---

### Task 3: Session store and feature merge

**Files:**
- Create: `web/session_store.py`
- Create: `web/feature_merge.py`
- Create: `web/tests/test_store.py`
- Create: `web/tests/test_merge.py`

**Interfaces:**
- Produces: `validate_id(value: str, kind: str) -> str`; `append_record(path: Path, record: dict) -> None`; `read_records(path: Path) -> list[dict]`; `has_session(records: list[dict], subject: str, session: str) -> bool`; `merge_session_features(vowel: dict, passage: dict) -> dict`.

- [ ] **Step 1: Write the failing tests**

`web/tests/test_store.py`:

```python
"""Append-only JSONL storage and identifier validation."""
import pytest

from web.session_store import validate_id, append_record, read_records, has_session


def test_validate_id_accepts_normal_values():
    assert validate_id("AMANDA", "subject") == "AMANDA"
    assert validate_id("CDR-01", "subject") == "CDR-01"
    assert validate_id("day-12", "session") == "day-12"


@pytest.mark.parametrize("value", ["../etc", "", "AMANDA", "A" * 40, "day 1"])
def test_validate_id_rejects_bad_values(value):
    with pytest.raises(ValueError):
        validate_id(value, "session")


def test_append_and_read_roundtrip(tmp_path):
    path = tmp_path / "sessions.jsonl"
    append_record(path, {"subject": "AMANDA", "session": "day1"})
    append_record(path, {"subject": "AMANDA", "session": "day2"})
    assert [r["session"] for r in read_records(path)] == ["day1", "day2"]


def test_read_missing_file_returns_empty(tmp_path):
    assert read_records(tmp_path / "missing.jsonl") == []


def test_has_session():
    records = [{"subject": "AMANDA", "session": "day1"}]
    assert has_session(records, "AMANDA", "day1") is True
    assert has_session(records, "AMANDA", "day2") is False
```

`web/tests/test_merge.py`:

```python
"""The three takes supply different features; merge must respect the split."""
from web.feature_merge import merge_session_features

VOWEL = {"jitter_local": 0.01, "shimmer_local": 0.06, "hnr_db": 20.0,
         "f0_mean_hz": 999.0}
PASSAGE = {"duration_s": 31.0, "f0_mean_hz": 120.0, "f0_sd_hz": 21.0,
           "intensity_db": 85.0, "pause_ratio": 0.04, "voiced_rate_hz": 95.0}


def test_vowel_supplies_voice_quality():
    merged = merge_session_features(VOWEL, PASSAGE)
    assert merged["jitter_local"] == 0.01
    assert merged["shimmer_local"] == 0.06
    assert merged["hnr_db"] == 20.0


def test_passage_supplies_rate_and_pitch():
    merged = merge_session_features(VOWEL, PASSAGE)
    assert merged["f0_mean_hz"] == 120.0
    assert merged["pause_ratio"] == 0.04
    assert merged["voiced_rate_hz"] == 95.0


def test_missing_values_become_none():
    merged = merge_session_features({}, {})
    assert merged["jitter_local"] is None
    assert merged["f0_mean_hz"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest web/tests/test_store.py web/tests/test_merge.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the store**

`web/session_store.py`:

```python
"""
Append-only JSONL storage for Baseline Drift sessions and check-in context.

Identifiers are validated before they touch the filesystem because the subject
and session names become path segments under web/data/recordings/.
"""
import json
import re
from pathlib import Path

SUBJECT_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,15}$")
SESSION_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,15}$")


def validate_id(value: str, kind: str) -> str:
    """Return a safe subject or session identifier, or raise ValueError."""
    pattern = SUBJECT_RE if kind == "subject" else SESSION_RE
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"invalid {kind}: {value!r}")
    return value


def append_record(path: Path, record: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_records(path: Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    records = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def has_session(records: list[dict], subject: str, session: str) -> bool:
    return any(r.get("subject") == subject and r.get("session") == session for r in records)
```

- [ ] **Step 4: Implement the merge**

`web/feature_merge.py`:

```python
"""
Merge per-task acoustic features into one session record.

The protocol assigns features by task: the sustained vowel carries jitter,
shimmer and harmonic-to-noise ratio; the fixed passage carries duration, pitch,
loudness, pausing and the voiced-rate proxy. Mixing sources would silently
change the baseline, so the mapping is explicit here and tested.
"""
PASSAGE_FEATURES = (
    "duration_s", "f0_mean_hz", "f0_sd_hz", "intensity_db",
    "pause_ratio", "voiced_rate_hz",
)
VOWEL_FEATURES = ("jitter_local", "shimmer_local", "hnr_db")
FEATURE_ORDER = PASSAGE_FEATURES + VOWEL_FEATURES


def merge_session_features(vowel: dict, passage: dict) -> dict:
    """Return one feature dict with None for any unavailable measurement."""
    merged = {feature: passage.get(feature) for feature in PASSAGE_FEATURES}
    merged.update({feature: vowel.get(feature) for feature in VOWEL_FEATURES})
    return {feature: merged.get(feature) for feature in FEATURE_ORDER}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest web/tests/test_store.py web/tests/test_merge.py -v`

Expected: 12 passed.

- [ ] **Step 6: Commit**

```powershell
git add web/session_store.py web/feature_merge.py web/tests/test_store.py web/tests/test_merge.py
git commit -m "feat: add session storage and per-task feature merge"
```

---

### Task 4: Session upload endpoint with WAV validation

**Files:**
- Modify: `web/server.py`
- Create: `web/tests/test_upload.py`

**Interfaces:**
- Consumes: `validate_id`, `append_record`, `read_records`, `has_session`, `merge_session_features`, `pipeline.voice_features.extract`.
- Produces: `POST /api/session` multipart (`subject`, `session`, `vowel`, `passage`, `free` optional) → `201 {"subject", "session", "features": {...}}`.

- [ ] **Step 1: Write the failing tests**

`web/tests/test_upload.py`:

```python
"""Upload validation, persistence, and duplicate rejection."""
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from web.server import create_app


def wav_bytes(path: Path, seconds: float = 1.0, freq: float = 220.0) -> bytes:
    sr = 16000
    t = np.arange(int(sr * seconds)) / sr
    signal = (0.3 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    sf.write(path, signal, sr)
    return path.read_bytes()


def test_upload_stores_one_merged_session(tmp_path):
    app = create_app(data_dir=tmp_path / "data", max_upload_bytes=5_000_000)
    client = TestClient(app)
    vowel = wav_bytes(tmp_path / "vowel.wav")
    passage = wav_bytes(tmp_path / "passage.wav", seconds=1.5)
    r = client.post(
        "/api/session",
        data={"subject": "AMANDA", "session": "day1"},
        files={
            "vowel": ("vowel.wav", vowel, "audio/wav"),
            "passage": ("passage.wav", passage, "audio/wav"),
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["subject"] == "AMANDA"
    assert body["session"] == "day1"
    assert set(body["features"]) >= {"f0_mean_hz", "jitter_local", "pause_ratio"}
    records = (tmp_path / "data" / "sessions.jsonl").read_text().splitlines()
    assert len(records) == 1
    assert (tmp_path / "data" / "recordings" / "AMANDA" / "day1_vowel.wav").exists()


def test_upload_rejects_non_wav(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path / "data"))
    r = client.post(
        "/api/session",
        data={"subject": "AMANDA", "session": "day1"},
        files={
            "vowel": ("vowel.webm", b"not a wav", "audio/webm"),
            "passage": ("passage.wav", wav_bytes(tmp_path / "p.wav"), "audio/wav"),
        },
    )
    assert r.status_code == 422


def test_upload_rejects_bad_subject(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path / "data"))
    wav = wav_bytes(tmp_path / "v.wav")
    r = client.post(
        "/api/session",
        data={"subject": "../etc", "session": "day1"},
        files={
            "vowel": ("v.wav", wav, "audio/wav"),
            "passage": ("p.wav", wav, "audio/wav"),
        },
    )
    assert r.status_code == 422


def test_upload_rejects_duplicate_session(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path / "data"))
    wav = wav_bytes(tmp_path / "v.wav")
    files = {
        "vowel": ("v.wav", wav, "audio/wav"),
        "passage": ("p.wav", wav, "audio/wav"),
    }
    assert client.post("/api/session", data={"subject": "AMANDA", "session": "day1"},
                       files=files).status_code == 201
    assert client.post("/api/session", data={"subject": "AMANDA", "session": "day1"},
                       files=files).status_code == 409


def test_upload_rejects_oversized_file(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path / "data", max_upload_bytes=100))
    wav = wav_bytes(tmp_path / "v.wav")
    r = client.post(
        "/api/session",
        data={"subject": "AMANDA", "session": "day1"},
        files={
            "vowel": ("v.wav", wav, "audio/wav"),
            "passage": ("p.wav", wav, "audio/wav"),
        },
    )
    assert r.status_code == 413
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest web/tests/test_upload.py -v`

Expected: FAIL with 404 for `/api/session`.

- [ ] **Step 3: Implement the endpoint**

Replace `web/server.py` with:

```python
"""
Baseline Drift local server.

Serves the one-page crew UI and the pipeline endpoints on 127.0.0.1 only.
No network calls leave this process; the browser page loads no external assets.
"""
import sys
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web.feature_merge import merge_session_features            # noqa: E402
from web.session_store import (                                 # noqa: E402
    append_record, has_session, read_records, validate_id,
)

MAX_UPLOAD_DEFAULT = 25 * 1024 * 1024


def is_wav(blob: bytes) -> bool:
    """A WAV file starts with RIFF and declares WAVE at byte 8. Cheap, exact."""
    return len(blob) >= 44 and blob[:4] == b"RIFF" and blob[8:12] == b"WAVE"


def read_upload(upload: UploadFile, max_bytes: int) -> bytes:
    blob = upload.file.read()
    if len(blob) > max_bytes:
        raise HTTPException(status_code=413, detail=f"{upload.filename} is too large")
    if not is_wav(blob):
        raise HTTPException(status_code=422, detail=f"{upload.filename} is not a PCM WAV")
    return blob


def create_app(data_dir: Path | None = None, static_dir: Path | None = None,
               max_upload_bytes: int = MAX_UPLOAD_DEFAULT) -> FastAPI:
    """Build the app. Tests pass temp paths; production uses web/data and web/app."""
    data = Path(data_dir or (Path(__file__).parent / "data"))
    static = Path(static_dir or (Path(__file__).parent / "app"))
    data.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="Baseline Drift", docs_url=None, redoc_url=None)
    app.state.data_dir = data
    app.state.static_dir = static

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "offline": True}

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(static / "index.html", media_type="text/html")

    @app.get("/app.js")
    def app_js() -> FileResponse:
        return FileResponse(static / "app.js", media_type="text/javascript")

    @app.get("/styles.css")
    def styles() -> FileResponse:
        return FileResponse(static / "styles.css", media_type="text/css")

    @app.post("/api/session", status_code=201)
    def create_session(
        subject: str = Form(...),
        session: str = Form(...),
        vowel: UploadFile = File(...),
        passage: UploadFile = File(...),
        free: UploadFile | None = File(None),
    ) -> dict:
        try:
            subject = validate_id(subject, "subject")
            session = validate_id(session, "session")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        sessions_path = data / "sessions.jsonl"
        records = read_records(sessions_path)
        if has_session(records, subject, session):
            raise HTTPException(status_code=409, detail="session already recorded")

        vowel_blob = read_upload(vowel, max_upload_bytes)
        passage_blob = read_upload(passage, max_upload_bytes)
        free_blob = read_upload(free, max_upload_bytes) if free else None

        recording_dir = data / "recordings" / subject
        recording_dir.mkdir(parents=True, exist_ok=True)
        vowel_path = recording_dir / f"{session}_vowel.wav"
        passage_path = recording_dir / f"{session}_passage.wav"
        vowel_path.write_bytes(vowel_blob)
        passage_path.write_bytes(passage_blob)
        saved = {"vowel": vowel_path.name, "passage": passage_path.name}
        if free_blob:
            free_path = recording_dir / f"{session}_free.wav"
            free_path.write_bytes(free_blob)
            saved["free"] = free_path.name

        from pipeline.voice_features import extract
        features = merge_session_features(extract(vowel_path), extract(passage_path))
        record = {
            "subject": subject, "session": session,
            "file": passage_path.name, "files": saved,
            "features": features,
        }
        append_record(sessions_path, record)
        return {"subject": subject, "session": session, "features": features}

    return app


app = create_app()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest web/tests/test_upload.py -v`

Expected: 5 passed.

- [ ] **Step 5: Commit**

```powershell
git add web/server.py web/tests/test_upload.py
git commit -m "feat: accept validated WAV takes and store merged sessions"
```

---

### Task 5: Check-in questions and context endpoint

**Files:**
- Create: `web/context_builder.py`
- Modify: `web/server.py`
- Create: `web/tests/test_context.py`

**Interfaces:**
- Consumes: `checkin_agent.QUESTIONS`, `checkin_agent.parse_plain`.
- Produces: `build_explains(answers: dict) -> dict[str, list[str]]`; `GET /api/questions`; `POST /api/context` → `201 {"explains": {...}}`.

- [ ] **Step 1: Write the failing tests**

`web/tests/test_context.py`:

```python
"""The explains map must match the rules the CLI check-in already uses."""
from pipeline.checkin_agent import QUESTIONS, parse_plain
from web.context_builder import build_explains


def test_cold_licenses_voice_quality_and_pitch():
    explains = build_explains({"cold_or_congestion": True})
    assert set(explains["hnr_db"]) == {"cold_or_congestion"}
    assert "f0_mean_hz" in explains
    assert "pause_ratio" not in explains


def test_cough_does_not_license_rate():
    explains = build_explains({"cough": True})
    assert "hnr_db" in explains
    assert "voiced_rate_hz" not in explains


def test_short_sleep_licenses_rate_and_pausing():
    explains = build_explains({"sleep_hours": 4.0})
    assert set(explains["voiced_rate_hz"]) == {"sleep_hours"}
    assert "pause_ratio" in explains


def test_normal_sleep_licenses_nothing():
    assert build_explains({"sleep_hours": 7.0}) == {}


def test_headache_licenses_nothing():
    assert build_explains({"headache": True}) == {}


def test_reclined_posture_licenses_pitch_and_pausing():
    explains = build_explains({"posture": "reclined on the couch"})
    assert "f0_mean_hz" in explains
    assert "pause_ratio" in explains


def test_sitting_posture_licenses_nothing():
    assert build_explains({"posture": "sitting"}) == {}


def test_setup_change_licenses_everything():
    explains = build_explains({"setup_changed": True})
    assert len(explains) == 8


def test_parity_with_cli_parser():
    answers = {q["field"]: parse_plain("yes", q["type"]) for q in QUESTIONS}
    explains = build_explains(answers)
    assert "hnr_db" in explains
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest web/tests/test_context.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the context builder**

`web/context_builder.py`:

```python
"""
Turn structured check-in answers into the explains map.

The rules mirror pipeline/checkin_agent.py: a true yes/no or a short sleep can
account for specific features; non-upright posture licenses pitch and pausing;
headache licenses nothing because it has no established acoustic signature.
Keeping the copy here lets the web app share the CLI's field definitions while
staying import-safe for tests.
"""
import re

from pipeline.checkin_agent import QUESTIONS

POSTURE_RE = re.compile(r"reclin|lying|lie|supine|lay|float|weightless", re.I)
POSTURE_FEATURES = ["f0_mean_hz", "f0_sd_hz", "intensity_db", "hnr_db", "pause_ratio"]


def build_explains(answers: dict) -> dict:
    """Return feature -> [reported reasons] for movements that are accounted for."""
    explains: dict[str, list[str]] = {}
    for question in QUESTIONS:
        field = question["field"]
        value = answers.get(field)
        triggered = value is True or (
            question["type"] == "number"
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and value < 6
        )
        licensed = list(question["explains"])
        if field == "posture" and isinstance(value, str) and POSTURE_RE.search(value):
            triggered = True
            licensed = POSTURE_FEATURES
        if triggered and licensed:
            for feature in licensed:
                explains.setdefault(feature, []).append(field)
    return explains
```

- [ ] **Step 4: Add the endpoints**

In `web/server.py`, add imports and routes inside `create_app`:

```python
from web.context_builder import build_explains  # noqa: E402
from pipeline.checkin_agent import QUESTIONS    # noqa: E402
```

```python
    @app.get("/api/questions")
    def questions() -> list[dict]:
        return [{"field": q["field"], "ask": q["ask"], "type": q["type"]}
                for q in QUESTIONS]

    @app.post("/api/context", status_code=201)
    def create_context(payload: dict) -> dict:
        try:
            subject = validate_id(payload.get("subject"), "subject")
            session = validate_id(payload.get("session"), "session")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        answers = payload.get("answers")
        if not isinstance(answers, dict):
            raise HTTPException(status_code=422, detail="answers must be an object")
        explains = build_explains(answers)
        append_record(data / "context.jsonl", {
            "subject": subject, "session": session,
            "answers": answers, "explains": explains, "backend": "none",
        })
        return {"explains": explains}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest web/tests/test_context.py -v`

Expected: 9 passed.

- [ ] **Step 6: Commit**

```powershell
git add web/context_builder.py web/server.py web/tests/test_context.py
git commit -m "feat: add check-in questions and explains endpoint"
```

---

### Task 6: Report endpoint

**Files:**
- Create: `web/reporting.py`
- Modify: `web/server.py`
- Create: `web/tests/test_report.py`

**Interfaces:**
- Consumes: `voice_drift.analyse`, `voice_drift.load_context`, `voice_drift.MIN_CHANGE`.
- Produces: `build_report(records, context, subject, n_baseline=3, z_threshold=2.0, min_run=2) -> dict`; `GET /api/report?subject=AMANDA`.

Report JSON schema:

```json
{
  "subject": "AMANDA",
  "state": "empty|baseline|stable|findings",
  "session_count": 4,
  "n_baseline": 3,
  "baseline_progress": {"have": 2, "need": 3},
  "headline": "1 change without a reported explanation",
  "findings": [
    {"feature": "pause_ratio", "label": "Pausing", "phrase": "more pausing",
     "value": 0.13, "unit": "", "baseline_mean": 0.055, "baseline_sd": 0.005,
     "z": 15.0, "delta": 0.075, "run_length": 2, "explained": [],
     "explained_by": [], "series": [0.05, 0.06, 0.055, 0.12, 0.13],
     "flagged_indices": [3, 4]}
  ],
  "stable_features": [{"feature": "hnr_db", "label": "Voice clarity"}]
}
```

- [ ] **Step 1: Write the failing tests**

`web/tests/test_report.py`:

```python
"""Report JSON states, ordering, and context attachment."""
from web.reporting import build_report


def record(session, **features):
    base = {k: None for k in (
        "duration_s", "f0_mean_hz", "f0_sd_hz", "intensity_db",
        "jitter_local", "shimmer_local", "hnr_db", "pause_ratio",
        "voiced_rate_hz")}
    base.update(features)
    return {"subject": "AMANDA", "session": session, "features": base}


def baseline_records():
    return [
        record("day1", intensity_db=84.0, pause_ratio=0.050, f0_mean_hz=120.0),
        record("day2", intensity_db=85.0, pause_ratio=0.060, f0_mean_hz=121.0),
        record("day3", intensity_db=86.0, pause_ratio=0.055, f0_mean_hz=119.0),
    ]


def test_empty_state():
    report = build_report([], {}, "AMANDA")
    assert report["state"] == "empty"
    assert report["findings"] == []


def test_baseline_state_reports_progress():
    report = build_report(baseline_records()[:2], {}, "AMANDA")
    assert report["state"] == "baseline"
    assert report["baseline_progress"] == {"have": 2, "need": 3}


def test_stable_state_when_nothing_moves():
    records = baseline_records() + [
        record("day4", intensity_db=85.0, pause_ratio=0.055, f0_mean_hz=120.0),
    ]
    report = build_report(records, {}, "AMANDA")
    assert report["state"] == "stable"
    assert report["findings"] == []


def test_unexplained_findings_come_first():
    records = baseline_records() + [
        record("day4", intensity_db=80.0, pause_ratio=0.120, f0_mean_hz=120.0),
        record("day5", intensity_db=79.5, pause_ratio=0.130, f0_mean_hz=120.5),
    ]
    context = {("AMANDA", "day5"): {"intensity_db": ["cold_or_congestion"]}}
    report = build_report(records, context, "AMANDA")
    assert report["state"] == "findings"
    first = report["findings"][0]
    assert first["feature"] == "pause_ratio"
    assert first["explained"] == []
    explained = [f for f in report["findings"] if f["feature"] == "intensity_db"][0]
    assert explained["explained"] == ["cold_or_congestion"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest web/tests/test_report.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement reporting**

`web/reporting.py`:

```python
"""
Build the report JSON the one-page UI renders.

Findings come from the same analyse() the CLI uses, so the UI cannot drift from
the validated gate logic. Only presentation is added here: labels, units,
series, and the explained-versus-unexplained ordering.
"""
from collections import defaultdict

from pipeline.voice_drift import MIN_CHANGE, analyse

LABEL = {
    "f0_mean_hz": "Pitch", "f0_sd_hz": "Pitch variation",
    "intensity_db": "Loudness", "jitter_local": "Pitch steadiness",
    "shimmer_local": "Loudness steadiness", "hnr_db": "Voice clarity",
    "pause_ratio": "Pausing", "voiced_rate_hz": "Speaking rate",
}
UNITS = {
    "f0_mean_hz": " Hz", "f0_sd_hz": " Hz", "intensity_db": " dB",
    "jitter_local": "", "shimmer_local": "", "hnr_db": " dB",
    "pause_ratio": "", "voiced_rate_hz": "/s",
}


def _findings_for(stats, findings, subject, records, context):
    by_feature = defaultdict(list)
    for finding in findings:
        by_feature[finding["feature"]].append(finding)
    session_names = [r["session"] for r in records]

    rows = []
    for feature, items in by_feature.items():
        latest = items[-1]
        reasons = context.get((subject, latest["session"]), {}).get(feature, [])
        flagged = [session_names.index(item["session"]) for item in items]
        rows.append({
            "feature": feature,
            "label": LABEL.get(feature, feature),
            "phrase": latest["phrase"],
            "value": latest["value"],
            "unit": UNITS.get(feature, ""),
            "baseline_mean": latest["baseline_mean"],
            "baseline_sd": round(stats[feature]["sd"], 4),
            "z": latest["z"],
            "delta": latest["delta"],
            "run_length": latest.get("run_length", len(items)),
            "explained": reasons,
            "explained_by": reasons,
            "series": [r["features"].get(feature) for r in records],
            "flagged_indices": flagged,
        })
    return sorted(rows, key=lambda row: (bool(row["explained"]), row["feature"]))


def build_report(records, context, subject, n_baseline=3, z_threshold=2.0, min_run=2):
    """Return the report state for one subject. Records stay in append order."""
    subject_records = [r for r in records if r.get("subject") == subject]

    base = {
        "subject": subject,
        "state": "empty",
        "session_count": len(subject_records),
        "n_baseline": n_baseline,
        "baseline_progress": {"have": min(len(subject_records), n_baseline),
                              "need": n_baseline},
        "headline": "No sessions yet",
        "findings": [],
        "stable_features": [],
    }
    if not subject_records:
        return base
    if len(subject_records) < n_baseline:
        base["state"] = "baseline"
        base["headline"] = (f"Building your baseline — {len(subject_records)} "
                            f"of {n_baseline} sessions")
        return base

    stats, findings = analyse(subject_records, n_baseline, z_threshold, min_run)
    rows = _findings_for(stats, findings, subject, subject_records, context)
    by_feature = {row["feature"] for row in rows}
    base["stable_features"] = [
        {"feature": feature, "label": LABEL.get(feature, feature)}
        for feature in MIN_CHANGE if feature in stats and feature not in by_feature
    ]
    base["findings"] = rows

    if not findings:
        base["state"] = "stable"
        base["headline"] = "Nothing moved far enough from your baseline to report"
        return base

    unexplained = sum(1 for row in rows if not row["explained"])
    base["state"] = "findings"
    if unexplained:
        base["headline"] = (f"{unexplained} change{'s' if unexplained != 1 else ''} "
                            f"without a reported explanation")
    else:
        base["headline"] = "Everything that moved has a reported explanation"
    return base
```

- [ ] **Step 4: Add the endpoint**

In `web/server.py`, add:

```python
from web.reporting import build_report  # noqa: E402
from web.session_store import read_records  # already imported
```

```python
    @app.get("/api/report")
    def report(subject: str) -> dict:
        try:
            subject = validate_id(subject, "subject")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        records = read_records(data / "sessions.jsonl")
        context_records = read_records(data / "context.jsonl")
        context = {(r["subject"], r["session"]): r.get("explains", {})
                   for r in context_records}
        return build_report(records, context, subject)
```

Note: the analyse signature is `analyse(records, n_baseline, z_threshold, min_run=2)`; passing positionally matches the pipeline.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest web/tests/test_report.py -v`

Expected: 4 passed.

- [ ] **Step 6: Commit**

```powershell
git add web/reporting.py web/server.py web/tests/test_report.py
git commit -m "feat: add report endpoint with unexplained-first ordering"
```

---

### Task 7: Record state UI

**Files:**
- Modify: `web/app/index.html`
- Modify: `web/app/app.js`
- Modify: `web/app/styles.css`
- Create: `web/tests/test_ui_contract.py`

**Interfaces:**
- Consumes: `POST /api/session`.
- Produces: DOM IDs `#record`, `#record-start`, `#take-status`, `#level-meter`, `#session-label`, `#subject`, `#to-checkin`; `recordTake(task, seconds) -> Promise<Blob>`; `encodeWav(channels, sampleRate) -> Blob`.

- [ ] **Step 1: Write the failing static contract test**

`web/tests/test_ui_contract.py`:

```python
"""The UI must expose the IDs the flow depends on and contain no external calls."""
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def test_record_ids_exist():
    html = (APP / "index.html").read_text(encoding="utf-8")
    for element_id in ("record", "record-start", "take-status", "level-meter",
                       "session-label", "subject", "to-checkin"):
        assert f'id="{element_id}"' in html, element_id


def test_three_take_flow_is_wired():
    js = (APP / "app.js").read_text(encoding="utf-8")
    for token in ("vowel", "passage", "free", "/api/session", "encodeWav"):
        assert token in js, token


def test_no_diagnostic_copy():
    text = "".join((APP / name).read_text(encoding="utf-8")
                   for name in ("index.html", "app.js", "styles.css")).lower()
    for banned in ("fatigued", "stressed", "you appear", "you seem"):
        assert banned not in text, banned
    assert "nothing here is a diagnosis" in text


def test_no_external_assets_anywhere():
    network = re.compile(
        r'(?:src|href)\s*=\s*["\']https?://'
        r'|fetch\(\s*["\']https?://'
        r'|@import\s+(?:url\()?["\']?https?://'
        r'|fonts\.(?:googleapis|gstatic)\.com',
        re.I,
    )
    for name in ("index.html", "app.js", "styles.css"):
        text = (APP / name).read_text(encoding="utf-8")
        assert not network.search(text), name
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest web/tests/test_ui_contract.py -v`

Expected: FAIL on missing IDs.

- [ ] **Step 3: Build the record state**

`web/app/index.html` (record section; keep the header, status, and script tags from Task 2):

```html
  <section id="record" class="panel" aria-labelledby="record-title">
    <h2 id="record-title">Record</h2>
    <div class="field">
      <label for="subject">Crew member</label>
      <input id="subject" name="subject" value="AMANDA" autocomplete="off" spellcheck="false">
    </div>
    <div class="field">
      <label for="session-label">Mission day</label>
      <input id="session-label" name="session" value="day1" autocomplete="off" spellcheck="false">
    </div>
    <p id="take-status" role="status" aria-live="polite">Ready. You will record three takes.</p>
    <div id="level-meter" class="meter" role="meter" aria-label="Microphone level"
         aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><span></span></div>
    <div class="actions">
      <button id="record-start" type="button">Start recording</button>
      <button id="to-checkin" type="button" class="secondary" disabled>Continue to check-in</button>
    </div>
  </section>
```

Add to `styles.css`:

```css
.field { display: grid; gap: var(--space-1); margin-bottom: var(--space-3); }
label { font-size: 12px; text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-muted); }
input {
  min-height: 44px; padding: 0 var(--space-2); background: var(--surface-2);
  color: var(--text-primary); border: 1px solid var(--line); border-radius: var(--radius);
  font: inherit;
}
.meter { height: 8px; background: var(--surface-2); border-radius: 4px; overflow: hidden; margin: var(--space-3) 0; }
.meter span { display: block; height: 100%; width: 0; background: var(--series-1); transition: width 80ms linear; }
.actions { display: flex; gap: var(--space-2); margin-top: var(--space-3); }
```

`web/app/app.js` (complete file for this task):

```javascript
"use strict";

const state = {
  subject: "AMANDA",
  session: "day1",
  takes: {},
};

const TAKES = [
  { key: "vowel", label: "sustained \"ah\"", seconds: 5 },
  { key: "passage", label: "fixed passage", seconds: 30 },
  { key: "free", label: "free speech", seconds: 60 },
];

function showState(name) {
  for (const id of ["record", "checkin", "report"]) {
    document.getElementById(id).hidden = id !== name;
  }
}

function setStatus(text) {
  document.getElementById("status").textContent = text;
}

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}

function encodeWav(channels, sampleRate) {
  const numFrames = channels[0].length;
  const bytesPerSample = 2;
  const blockAlign = channels.length * bytesPerSample;
  const buffer = new ArrayBuffer(44 + numFrames * blockAlign);
  const view = new DataView(buffer);
  const writeStr = (offset, text) => {
    for (let i = 0; i < text.length; i += 1) view.setUint8(offset + i, text.charCodeAt(i));
  };
  writeStr(0, "RIFF");
  view.setUint32(4, 36 + numFrames * blockAlign, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, channels.length, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * blockAlign, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, 16, true);
  writeStr(36, "data");
  view.setUint32(40, numFrames * blockAlign, true);
  let offset = 44;
  for (let frame = 0; frame < numFrames; frame += 1) {
    for (let channel = 0; channel < channels.length; channel += 1) {
      const sample = Math.max(-1, Math.min(1, channels[channel][frame]));
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
      offset += 2;
    }
  }
  return new Blob([view], { type: "audio/wav" });
}

async function recordTake(task, maxSeconds) {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const context = new AudioContext();
  const source = context.createMediaStreamSource(stream);
  const analyser = context.createAnalyser();
  analyser.fftSize = 2048;
  source.connect(analyser);

  const meter = document.querySelector("#level-meter span");
  const meterRoot = document.getElementById("level-meter");
  const data = new Uint8Array(analyser.fftSize);
  let raf = 0;
  const draw = () => {
    analyser.getByteTimeDomainData(data);
    let peak = 0;
    for (const value of data) peak = Math.max(peak, Math.abs(value - 128) / 128);
    const pct = Math.round(peak * 100);
    meter.style.width = `${pct}%`;
    meterRoot.setAttribute("aria-valuenow", String(pct));
    raf = requestAnimationFrame(draw);
  };
  draw();

  const recorder = new MediaRecorder(stream);
  const chunks = [];
  recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
  const stopped = new Promise((resolve) => { recorder.onstop = resolve; });
  recorder.start();

  await new Promise((resolve) => setTimeout(resolve, maxSeconds * 1000));
  recorder.stop();
  await stopped;
  cancelAnimationFrame(raf);
  stream.getTracks().forEach((track) => track.stop());

  const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
  const audio = await context.decodeAudioData(await blob.arrayBuffer());
  await context.close();
  return encodeWav([audio.getChannelData(0)], audio.sampleRate);
}

async function runSession() {
  state.subject = document.getElementById("subject").value.trim().toUpperCase();
  state.session = document.getElementById("session-label").value.trim().toLowerCase();
  const status = document.getElementById("take-status");
  const button = document.getElementById("record-start");
  button.disabled = true;
  try {
    for (const take of TAKES) {
      status.textContent = `Recording ${take.label} (${take.seconds}s)…`;
      state.takes[take.key] = await recordTake(take.key, take.seconds);
      status.textContent = `Captured ${take.label}.`;
    }
    status.textContent = "Uploading to the local pipeline…";
    const form = new FormData();
    form.append("subject", state.subject);
    form.append("session", state.session);
    for (const take of TAKES) {
      form.append(take.key, state.takes[take.key], `${state.session}_${take.key}.wav`);
    }
    await api("/api/session", { method: "POST", body: form });
    status.textContent = "Session stored on this machine.";
    document.getElementById("to-checkin").disabled = false;
  } catch (error) {
    status.textContent = `Recording failed: ${error.message}. Check microphone permission and try again.`;
    button.disabled = false;
  }
}

document.getElementById("record-start").addEventListener("click", runSession);
document.getElementById("to-checkin").addEventListener("click", () => showState("checkin"));
showState("record");
```

**Manual checklist (run in Chrome/Edge on the demo laptop):**
- Record button asks for mic permission; level meter moves during speech.
- Three takes complete in order; status text updates.
- Upload succeeds with real WAVs in `web/data/recordings/<SUBJECT>/`.
- Denying permission shows a plain-language error and re-enables the button.
- Keyboard-only flow works; the page loads with the network disabled.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest web/tests/test_ui_contract.py -v`

Expected: 4 passed.

- [ ] **Step 5: Commit**

```powershell
git add web/app web/tests/test_ui_contract.py
git commit -m "feat: add record state with WAV capture and level meter"
```

---

### Task 8: Check-in state UI

**Files:**
- Modify: `web/app/index.html`
- Modify: `web/app/app.js`
- Modify: `web/app/styles.css`

**Interfaces:**
- Consumes: `GET /api/questions`, `POST /api/context`.
- Produces: DOM IDs `#checkin-form`, `#question`, `#question-label`, `#answer`, `#checkin-next`, `#checkin-skip`, `#to-report`.

- [ ] **Step 1: Write the failing static test**

Add to `web/tests/test_ui_contract.py`:

```python
def test_checkin_ids_and_labels():
    html = (APP / "index.html").read_text(encoding="utf-8")
    for element_id in ("checkin-form", "question-label", "answer",
                       "checkin-next", "checkin-skip", "to-report"):
        assert f'id="{element_id}"' in html, element_id
    js = (APP / "app.js").read_text(encoding="utf-8")
    for token in ("/api/questions", "/api/context", "buildAnswers"):
        assert token in js, token
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest web/tests/test_ui_contract.py::test_checkin_ids_and_labels -v`

Expected: FAIL.

- [ ] **Step 3: Implement the check-in state**

`index.html` check-in section:

```html
  <section id="checkin" class="panel" hidden aria-labelledby="checkin-title">
    <h2 id="checkin-title">Check-in</h2>
    <p class="sub">Answers are context, not a diagnosis. Skip anything you prefer not to answer.</p>
    <form id="checkin-form">
      <div class="field">
        <label id="question-label" for="answer">Question</label>
        <input id="answer" name="answer" autocomplete="off">
      </div>
      <div class="actions">
        <button id="checkin-next" type="submit">Next</button>
        <button id="checkin-skip" type="button" class="secondary">Skip</button>
      </div>
    </form>
    <div class="actions">
      <button id="to-report" type="button" class="secondary" disabled>Open report</button>
    </div>
  </section>
```

`app.js` additions:

```javascript
const checkin = { questions: [], index: 0, answers: {} };

function parseAnswer(type, raw) {
  const text = raw.trim();
  if (type === "yesno" || type === "yesno_inverted") {
    if (/^(yes|yeah|yep|yup|true)/i.test(text)) return true;
    if (/^(no|nope|nah|false|none)/i.test(text)) return false;
    return null;
  }
  if (type === "number") {
    const match = text.match(/-?\d+(?:\.\d+)?/);
    return match ? Number(match[0]) : null;
  }
  return text || null;
}

function buildAnswers() {
  return checkin.answers;
}

async function loadQuestions() {
  checkin.questions = await api("/api/questions");
  renderQuestion();
}

function renderQuestion() {
  const question = checkin.questions[checkin.index];
  if (!question) {
    document.getElementById("question-label").textContent = "All questions answered.";
    document.getElementById("answer").disabled = true;
    document.getElementById("checkin-next").disabled = true;
    document.getElementById("checkin-skip").disabled = true;
    return;
  }
  document.getElementById("question-label").textContent = question.ask;
  const answer = document.getElementById("answer");
  answer.value = "";
  answer.type = question.type === "number" ? "text" : "text";
  answer.focus();
}

function advanceCheckin(value) {
  const question = checkin.questions[checkin.index];
  if (question) checkin.answers[question.field] = value;
  checkin.index += 1;
  renderQuestion();
}

async function submitCheckin() {
  const question = checkin.questions[checkin.index];
  if (!question) return;
  const raw = document.getElementById("answer").value;
  advanceCheckin(parseAnswer(question.type, raw));
  if (checkin.index < checkin.questions.length) return;
  await api("/api/context", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      subject: state.subject, session: state.session, answers: buildAnswers(),
    }),
  });
  document.getElementById("to-report").disabled = false;
  setStatus("Check-in stored. Open the report when ready.");
}

document.getElementById("checkin-form").addEventListener("submit", (event) => {
  event.preventDefault();
  submitCheckin();
});
document.getElementById("checkin-skip").addEventListener("click", () => advanceCheckin(null));
document.getElementById("to-report").addEventListener("click", () => showState("report"));
document.getElementById("to-checkin").addEventListener("click", () => {
  showState("checkin");
  if (!checkin.questions.length) loadQuestions();
});
```

Note: Task 7 already wires `#to-checkin`; replace that listener with the version above so questions load once.

Add to `styles.css`:

```css
.sub { color: var(--text-muted); font-size: 13px; }
button:disabled { opacity: 0.45; cursor: not-allowed; }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest web/tests/test_ui_contract.py -v`

Expected: 5 passed.

- [ ] **Step 5: Commit**

```powershell
git add web/app
git commit -m "feat: add skippable check-in state"
```

---

### Task 9: Report state UI

**Files:**
- Modify: `web/app/index.html`
- Modify: `web/app/app.js`
- Modify: `web/app/styles.css`

**Interfaces:**
- Consumes: `GET /api/report?subject=...`.
- Produces: DOM IDs `#report-headline`, `#report-list`, `#baseline-note`, `#report-refresh`; `renderReport(data)`.

- [ ] **Step 1: Write the failing static test**

Add to `web/tests/test_ui_contract.py`:

```python
def test_report_ids_and_renderer():
    html = (APP / "index.html").read_text(encoding="utf-8")
    for element_id in ("report-headline", "report-list", "baseline-note", "report-refresh"):
        assert f'id="{element_id}"' in html, element_id
    js = (APP / "app.js").read_text(encoding="utf-8")
    for token in ("renderReport", "/api/report", "sparkline"):
        assert token in js, token
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest web/tests/test_ui_contract.py::test_report_ids_and_renderer -v`

Expected: FAIL.

- [ ] **Step 3: Implement the report state**

`index.html` report section:

```html
  <section id="report" class="panel" hidden aria-labelledby="report-title">
    <h2 id="report-title">Report</h2>
    <div id="report-headline" class="headline"></div>
    <p id="baseline-note" class="sub"></p>
    <div id="report-list" class="report-list"></div>
    <div class="actions">
      <button id="report-refresh" type="button" class="secondary">Refresh</button>
    </div>
  </section>
```

`app.js` additions:

```javascript
function sparkline(values, mean, sd, flagged) {
  const width = 220;
  const height = 44;
  const pad = 6;
  const clean = values.filter((value) => value !== null);
  if (clean.length < 2) return document.createElement("span");
  const lo = Math.min(...clean, mean - 2.5 * sd);
  const hi = Math.max(...clean, mean + 2.5 * sd);
  const span = hi - lo || 1;
  const x = (index) => pad + index * (width - 2 * pad) / Math.max(values.length - 1, 1);
  const y = (value) => height - pad - (value - lo) * (height - 2 * pad) / span;
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("width", String(width));
  svg.setAttribute("height", String(height));
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "trend across sessions with the baseline band");

  const band = document.createElementNS(ns, "rect");
  band.setAttribute("x", "0");
  band.setAttribute("y", String(Math.min(y(mean + sd), y(mean - sd))));
  band.setAttribute("width", String(width));
  band.setAttribute("height", String(Math.max(Math.abs(y(mean - sd) - y(mean + sd)), 1)));
  band.setAttribute("class", "band");
  svg.appendChild(band);

  const line = document.createElementNS(ns, "line");
  line.setAttribute("x1", "0");
  line.setAttribute("x2", String(width));
  line.setAttribute("y1", String(y(mean)));
  line.setAttribute("y2", String(y(mean)));
  line.setAttribute("class", "meanline");
  svg.appendChild(line);

  const points = [];
  values.forEach((value, index) => {
    if (value === null) return;
    const dot = document.createElementNS(ns, "circle");
    dot.setAttribute("cx", String(x(index)));
    dot.setAttribute("cy", String(y(value)));
    dot.setAttribute("r", flagged.includes(index) ? "4" : "2.5");
    dot.setAttribute("class", flagged.includes(index) ? "dot flag" : "dot");
    svg.appendChild(dot);
    points.push(`${x(index).toFixed(1)},${y(value).toFixed(1)}`);
  });

  const polyline = document.createElementNS(ns, "polyline");
  polyline.setAttribute("points", points.join(" "));
  polyline.setAttribute("class", "series");
  svg.appendChild(polyline);
  return svg;
}

function findingRow(finding) {
  const row = document.createElement("div");
  row.className = finding.explained.length ? "row" : "row open-row";

  const meta = document.createElement("div");
  meta.className = "meta";
  const label = document.createElement("div");
  label.className = "label";
  label.textContent = finding.label;
  const phrase = document.createElement("div");
  phrase.className = "phrase";
  phrase.textContent = finding.phrase;
  const detail = document.createElement("div");
  detail.className = "detail";
  detail.textContent = `${finding.value}${finding.unit} against your baseline of `
    + `${finding.baseline_mean}${finding.unit} · ${finding.run_length} `
    + `session${finding.run_length === 1 ? "" : "s"} running`;
  const tag = document.createElement("span");
  tag.className = finding.explained.length ? "tag explained" : "tag open";
  tag.textContent = finding.explained.length
    ? `accounted for: ${finding.explained.join(", ").replaceAll("_", " ")}`
    : "no reported explanation";

  meta.append(label, phrase, detail, tag);
  const spark = document.createElement("div");
  spark.className = "spark";
  spark.appendChild(sparkline(finding.series, finding.baseline_mean,
                              finding.baseline_sd, finding.flagged_indices));
  row.append(meta, spark);
  return row;
}

function renderReport(data) {
  document.getElementById("report-headline").textContent = data.headline;
  document.getElementById("baseline-note").textContent = data.state === "baseline"
    ? `Your baseline is built from your first ${data.n_baseline} sessions.`
    : "Measured against your own baseline. Shaded band is one standard deviation; "
      + "the dashed line is your baseline average.";
  const list = document.getElementById("report-list");
  list.replaceChildren();
  if (data.state === "empty") {
    const empty = document.createElement("p");
    empty.textContent = "No sessions yet. Record your first check-in to begin.";
    list.appendChild(empty);
    return;
  }
  if (data.state === "baseline") {
    const pending = document.createElement("p");
    pending.textContent = `Building your baseline — ${data.baseline_progress.have} of `
      + `${data.baseline_progress.need} sessions. No findings are reported yet.`;
    list.appendChild(pending);
    return;
  }
  if (!data.findings.length) {
    const stable = document.createElement("p");
    stable.textContent = "Nothing moved far enough from your baseline to report.";
    list.appendChild(stable);
    return;
  }
  for (const finding of data.findings) {
    list.appendChild(findingRow(finding));
  }
  const footer = document.createElement("p");
  footer.className = "sub";
  footer.textContent = "This describes what changed, not why. Ordinary causes are the "
    + "common ones: a head cold, a different microphone, the time of day, the room. "
    + "Nothing here is a diagnosis.";
  list.appendChild(footer);
}

async function loadReport() {
  setStatus("Building your report…");
  const data = await api(`/api/report?subject=${encodeURIComponent(state.subject)}`);
  renderReport(data);
  setStatus("");
}

document.getElementById("report-refresh").addEventListener("click", loadReport);
document.getElementById("to-report").addEventListener("click", () => {
  showState("report");
  loadReport();
});
```

Replace the earlier `#to-report` listener from Task 8 with this one; two listeners would render the report twice.

Add to `styles.css`:

```css
.headline { font-size: 17px; font-weight: 600; margin: var(--space-3) 0 var(--space-1); }
.report-list { margin-top: var(--space-3); }
.row {
  display: flex; gap: var(--space-4); align-items: center; justify-content: space-between;
  padding: var(--space-3) 0 var(--space-3) 14px; border-top: 1px solid var(--line);
  border-left: 2px solid transparent;
}
.row.open-row { border-left-color: var(--accent); }
.row .label { font-size: 12px; text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-muted); margin-bottom: 3px; }
.row .phrase { font-size: 16px; font-weight: 600; margin-bottom: 3px; }
.row .detail { color: var(--text-secondary); font-size: 13px; }
.tag { display: inline-block; margin-top: var(--space-2); font-size: 12px; padding: 2px 8px; border-radius: 3px; border: 1px solid var(--line); background: var(--surface-2); }
.tag.explained { color: var(--text-muted); }
.tag.open { color: var(--text-primary); border-color: var(--accent); }
.spark { flex: 0 0 auto; }
.band { fill: var(--surface-2); }
.meanline { stroke: var(--text-muted); stroke-width: 1; stroke-dasharray: 3 3; opacity: 0.6; }
.series { fill: none; stroke: var(--series-1); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.dot { fill: var(--series-1); stroke: var(--surface-0); stroke-width: 2; }
.dot.flag { fill: var(--accent); }
```

**Manual checklist:**
- Baseline state shows progress and no findings.
- Stable state shows the explicit "nothing moved" message.
- Findings list puts "no reported explanation" rows first.
- Report reflects the explained tag after a cold/cough check-in.
- Wording never names a diagnosis; "your baseline" appears.
- Contrast and focus states pass a quick keyboard walk.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest web/tests/test_ui_contract.py -v`

Expected: 6 passed.

- [ ] **Step 5: Commit**

```powershell
git add web/app
git commit -m "feat: render the descriptive report state"
```

---

### Task 10: End-to-end dry run, README, full suite

**Files:**
- Create: `web/tests/test_e2e.py`
- Modify: `web/README.md`
- Modify: `web/server.py` only if an integration bug appears.

**Interfaces:**
- Consumes: every endpoint above.
- Produces: a passing end-to-end test and run instructions.

- [ ] **Step 1: Write the failing end-to-end test**

`web/tests/test_e2e.py`:

```python
"""Six synthetic sessions: three baseline, three drifting, one report."""
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from pipeline.make_test_audio import utterance
from web.server import create_app

PLAN = [
    ("day1", 118, 0.80, 0.010, 0.15),
    ("day2", 121, 0.82, 0.011, 0.17),
    ("day3", 119, 0.79, 0.010, 0.14),
    ("day4", 104, 0.55, 0.019, 0.42),
    ("day5", 102, 0.52, 0.021, 0.45),
    ("day6", 105, 0.54, 0.020, 0.40),
]


def wav(tmp_path: Path, name: str, args) -> bytes:
    path = tmp_path / name
    sf.write(path, utterance(*args[1:]), 16000)
    return path.read_bytes()


def test_three_baseline_sessions_then_drift_report(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path / "data"))
    for session, f0, amp, jitter, pause in PLAN:
        blob = wav(tmp_path, f"{session}.wav", (session, f0, amp, jitter, pause))
        response = client.post(
            "/api/session",
            data={"subject": "AMANDA", "session": session},
            files={
                "vowel": (f"{session}_vowel.wav", blob, "audio/wav"),
                "passage": (f"{session}_passage.wav", blob, "audio/wav"),
            },
        )
        assert response.status_code == 201, response.text

    report = client.get("/api/report", params={"subject": "AMANDA"}).json()
    assert report["state"] == "findings"
    assert report["session_count"] == 6
    assert len(report["findings"]) >= 1
    text = (report["headline"] + " " + " ".join(f["phrase"] for f in report["findings"])).lower()
    for banned in ("fatigue", "stressed", "diagnosis", "normal range"):
        assert banned not in text
```

- [ ] **Step 2: Run test to verify it fails or exposes integration gaps**

Run: `python -m pytest web/tests/test_e2e.py -v`

Expected: 1 passed if earlier tasks are correct. If it fails, fix the specific integration issue, not the test.

- [ ] **Step 3: Write `web/README.md`**

```markdown
# Baseline Drift web UI

Run on the habitat machine, offline:

    python -m pip install -r web/requirements.txt
    python -m uvicorn web.server:app --host 127.0.0.1 --port 8765

Open http://127.0.0.1:8765. One page, three states: record, check-in, report.

## Demo checklist

1. Record three takes for mission day 1; confirm the session lands in `web/data/recordings/`.
2. Repeat for days 2–6. Use the same microphone and the same room.
3. After day 3 the report switches from baseline-building to scored findings.
4. A cold/cough check-in tags the matching features as accounted for.
5. Disconnect the network and reload; nothing breaks.
6. Confirm no external requests in the browser network panel.

## Tests

    python -m pytest web/tests -v

The end-to-end test generates synthetic sessions, so it proves the wiring without
needing real recordings. Real recordings still matter for the demo.
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest web/tests -v`

Expected: all tests pass (static, store, merge, upload, context, report, UI contract, e2e).

- [ ] **Step 5: Commit and push**

```powershell
git add web/tests/test_e2e.py web/README.md
git commit -m "test: prove the six-session demo path end to end"
git push origin main
```

---

## Self-Review Notes

- **Spec coverage:** Record/Check-in/Report states (Tasks 7–9), offline constraint (Tasks 2, 7, 9 tests), WAV capture (Task 7), per-person baseline and three gates (Task 6 reuses `voice_drift.analyse`), explained-versus-unexplained ordering (Task 6), descriptive wording (Tasks 7 and 9 tests), empty/loading/error states (Task 9 renderer and status regions), accessibility basics (labels, live regions, focus styles, 44px targets), OSD-575 validation (already in the repo, not re-implemented).
- **Type consistency:** `merge_session_features(vowel, passage)`, `build_explains(answers)`, `build_report(records, context, subject, n_baseline, z_threshold, min_run)`, and `create_app(data_dir, static_dir, max_upload_bytes)` are used consistently in tests and call sites.
- **No placeholders:** every code step contains runnable code; UI tasks include the complete additions and manual checks.
- **Scope:** one subsystem (the web UI and its local wiring). The pipeline and validation stay untouched.
