"""
Baseline Drift local server.

Serves the one-page crew UI and the pipeline endpoints on 127.0.0.1 only.
No network calls leave this process; the browser page loads no external assets.
"""
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web.context_builder import (                                # noqa: E402
    build_answers_from_raw, build_explains,
)
from web.feature_merge import merge_session_features            # noqa: E402
from web.reporting import build_report                          # noqa: E402
from web.session_store import (                                 # noqa: E402
    append_record, has_session, read_records, remove_session, validate_id,
)
from pipeline.checkin_agent import QUESTIONS                    # noqa: E402

MAX_UPLOAD_DEFAULT = 25 * 1024 * 1024


def default_data_dir() -> Path:
    """
    Writable data location for both source runs and the packaged executable.

    A PyInstaller one-file build unpacks into a temporary directory, so data
    written beside the source module would disappear on exit. In a frozen
    build the exe's own folder is the transparent, inspectable location; an
    explicit BASELINE_DRIFT_DATA override keeps tests and demos disposable.
    """
    override = os.environ.get("BASELINE_DRIFT_DATA")
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "data"
    return Path(__file__).parent / "data"


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
    """Build the app. Tests pass temp paths; production uses the data dir above."""
    data = Path(data_dir or default_data_dir())
    static = Path(static_dir or (Path(__file__).parent / "app"))
    data.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="Baseline Drift", docs_url=None, redoc_url=None)
    app.state.data_dir = data
    app.state.static_dir = static

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "offline": True}

    @app.get("/api/next-session")
    def next_session(subject: str) -> dict:
        """Suggest the next flight day so nobody has to remember the count."""
        try:
            subject = validate_id(subject, "subject")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        mine = [r for r in read_records(data / "sessions.jsonl")
                if r.get("subject") == subject]
        numbers = [int(m.group(1)) for r in mine
                   if (m := re.fullmatch(r"(?:fd|day)(\d+)", r.get("session", "")))]
        day = max(numbers + [len(mine)]) + 1
        return {"subject": subject, "flight_day": day, "session": f"fd{day}",
                "session_count": len(mine)}

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

        # The browser sends raw text so the server can apply the CLI's parser
        # and keep both the parsed value and the words the crew member used.
        # Structured answers remain accepted for older clients and fixtures.
        raw = payload.get("raw")
        if raw is not None:
            try:
                answers = build_answers_from_raw(raw)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        else:
            answers = payload.get("answers")
            if not isinstance(answers, dict):
                raise HTTPException(status_code=422, detail="answers must be an object")
        explains = build_explains(answers)
        append_record(data / "context.jsonl", {
            "subject": subject, "session": session,
            "answers": answers, "explains": explains, "backend": "none",
        })
        return {"explains": explains}

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

    # The page is served from disk on this machine, so caching buys nothing
    # and a stale script against a newer page breaks the buttons.
    fresh = {"Cache-Control": "no-store"}

    @app.get("/")
    def index() -> HTMLResponse:
        # Stamp the script and stylesheet links with their modification time.
        # A browser that cached an older copy sees a new address and fetches
        # the current file, so the page can never run against a stale script.
        stamp = int(max((static / name).stat().st_mtime for name in ("app.js", "styles.css")))
        html = (static / "index.html").read_text(encoding="utf-8")
        html = html.replace('href="/styles.css"', f'href="/styles.css?v={stamp}"')
        html = html.replace('src="/app.js"', f'src="/app.js?v={stamp}"')
        return HTMLResponse(html, headers=fresh)

    @app.get("/sample_report.json")
    def sample_report() -> FileResponse:
        # A simulated crew member's report, built by web/make_sample.py, so the
        # report and trends can be explored before anyone has recorded.
        return FileResponse(static / "sample_report.json",
                            media_type="application/json", headers=fresh)

    @app.get("/app.js")
    def app_js() -> FileResponse:
        return FileResponse(static / "app.js", media_type="text/javascript", headers=fresh)

    @app.get("/styles.css")
    def styles() -> FileResponse:
        return FileResponse(static / "styles.css", media_type="text/css", headers=fresh)

    @app.post("/api/session", status_code=201)
    def create_session(
        subject: str = Form(...),
        session: str = Form(...),
        vowel: UploadFile = File(...),
        passage: UploadFile = File(...),
        free: UploadFile | None = File(None),
        replace: bool = Form(False),
    ) -> dict:
        try:
            subject = validate_id(subject, "subject")
            session = validate_id(session, "session")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        sessions_path = data / "sessions.jsonl"
        records = read_records(sessions_path)
        exists = has_session(records, subject, session)
        if exists and not replace:
            raise HTTPException(status_code=409, detail="session already recorded")

        vowel_blob = read_upload(vowel, max_upload_bytes)
        passage_blob = read_upload(passage, max_upload_bytes)
        free_blob = read_upload(free, max_upload_bytes) if free else None

        if exists:
            # A redo replaces the session and its check-in: answers given for
            # the discarded takes must not explain the new ones.
            remove_session(sessions_path, subject, session)
            remove_session(data / "context.jsonl", subject, session)

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
            # The laptop's own clock, with its UTC offset, so sessions can be
            # placed in time and time of day is available to the report.
            "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "file": passage_path.name, "files": saved,
            "features": features,
        }
        append_record(sessions_path, record)
        return {"subject": subject, "session": session, "features": features,
                "recorded_at": record["recorded_at"]}

    @app.delete("/api/session")
    def delete_session(subject: str, session: str) -> dict:
        """Remove one session for good: its measurements, check-in and audio."""
        try:
            subject = validate_id(subject, "subject")
            session = validate_id(session, "session")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        removed = remove_session(data / "sessions.jsonl", subject, session)
        if not removed:
            raise HTTPException(status_code=404, detail="no such session")
        remove_session(data / "context.jsonl", subject, session)
        files = 0
        recording_dir = data / "recordings" / subject
        for take in ("vowel", "passage", "free"):
            path = recording_dir / f"{session}_{take}.wav"
            if path.exists():
                path.unlink()
                files += 1
        return {"subject": subject, "session": session, "audio_files_deleted": files}

    return app


app = create_app()
