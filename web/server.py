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

from web.context_builder import build_explains                  # noqa: E402
from web.feature_merge import merge_session_features            # noqa: E402
from web.session_store import (                                 # noqa: E402
    append_record, has_session, read_records, validate_id,
)
from pipeline.checkin_agent import QUESTIONS                    # noqa: E402

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
