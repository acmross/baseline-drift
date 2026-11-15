"""
Baseline Drift local server.

Serves the one-page crew UI and the pipeline endpoints on 127.0.0.1 only.
No network calls leave this process; the browser page loads no external assets.

Hosted demo mode (BASELINE_DRIFT_HOSTED=1) is the one exception, and exists
only so someone can try the real pipeline without installing it. There each
visitor gets a private, temporary space keyed by a random cookie, and all of
it (recordings, measurements, check-in answers) is deleted within
RETENTION_SECONDS of that visitor's first request. The page says all of this in place of the privacy notice.
"""
import contextvars
import os
import re
import secrets
import shutil
import sys
import time
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
RETENTION_SECONDS = 2 * 60 * 60
MAX_VISITORS = 300
VISITOR_COOKIE = "bd_visitor"
VISITOR_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
_visitor: contextvars.ContextVar[str] = contextvars.ContextVar("visitor", default="shared")


class VisitorData:
    """Stands in for the data directory in hosted mode: every path resolves
    inside the current visitor's own folder, so visitors never see each other."""

    def __init__(self, base: Path):
        self.base = base
        self.last_sweep = 0.0

    def current(self) -> Path:
        folder = self.base / _visitor.get()
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
            (folder / ".started").touch()           # the clock starts here
        return folder

    def __truediv__(self, other) -> Path:
        return self.current() / other

    def sweep(self) -> None:
        """Delete every visitor space older than the retention time, counted
        from that visitor's first request, and the oldest ones past the cap."""
        now = time.time()
        if now - self.last_sweep < 60:
            return
        self.last_sweep = now

        def started(folder: Path) -> float:
            marker = folder / ".started"
            return (marker if marker.exists() else folder).stat().st_mtime

        folders = sorted((p for p in self.base.iterdir() if p.is_dir()), key=started)
        excess = len(folders) - MAX_VISITORS
        for index, folder in enumerate(folders):
            if index < excess or now - started(folder) > RETENTION_SECONDS:
                shutil.rmtree(folder, ignore_errors=True)


class VisitorMiddleware:
    """Gives each browser a random id cookie and scopes the request to it."""

    def __init__(self, app, store: VisitorData):
        self.app = app
        self.store = store

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        token = None
        for key, value in scope.get("headers", []):
            if key == b"cookie":
                for part in value.decode("latin-1").split(";"):
                    name, _, found = part.strip().partition("=")
                    if name == VISITOR_COOKIE and VISITOR_RE.match(found):
                        token = found
        fresh_visitor = token is None
        if fresh_visitor:
            token = secrets.token_urlsafe(24)
        self.store.sweep()                 # every request, at most once a minute
        reset = _visitor.set(token)

        async def send_with_cookie(message):
            if fresh_visitor and message["type"] == "http.response.start":
                cookie = (f"{VISITOR_COOKIE}={token}; Path=/; Max-Age={RETENTION_SECONDS}; "
                          "HttpOnly; SameSite=Lax; Secure")
                message.setdefault("headers", []).append((b"set-cookie", cookie.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_cookie)
        finally:
            _visitor.reset(reset)


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
               max_upload_bytes: int = MAX_UPLOAD_DEFAULT,
               hosted: bool | None = None) -> FastAPI:
    """Build the app. Tests pass temp paths; production uses the data dir above."""
    if hosted is None:
        hosted = os.environ.get("BASELINE_DRIFT_HOSTED") == "1"
    base = Path(data_dir or default_data_dir())
    static = Path(static_dir or (Path(__file__).parent / "app"))
    base.mkdir(parents=True, exist_ok=True)
    data = VisitorData(base) if hosted else base

    app = FastAPI(title="Baseline Drift", docs_url=None, redoc_url=None)
    if hosted:
        app.add_middleware(VisitorMiddleware, store=data)
    app.state.hosted = hosted
    app.state.data_dir = base
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
        if hosted:
            minutes = RETENTION_SECONDS // 60
            html = html.replace(
                "<script src=",
                f"<script>window.BASELINE_DRIFT_HOSTED = {minutes};</script>\n<script src=", 1)
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

    TAKE_NAMES = ("vowel", "passage", "free")

    def _find_session(subject: str, session: str) -> tuple[str, str, dict]:
        try:
            subject = validate_id(subject, "subject")
            session = validate_id(session, "session")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        for record in read_records(data / "sessions.jsonl"):
            if record.get("subject") == subject and record.get("session") == session:
                return subject, session, record
        raise HTTPException(status_code=404, detail="no such session")

    @app.get("/api/session-detail")
    def session_detail(subject: str, session: str) -> dict:
        """One saved session: its measurements, check-in answers and takes."""
        from web.reporting import session_detail as build_detail
        subject, session, record = _find_session(subject, session)
        answers = None
        for entry in read_records(data / "context.jsonl"):
            if entry.get("subject") == subject and entry.get("session") == session:
                answers = entry.get("answers", {})
        recording_dir = data / "recordings" / subject
        detail = build_detail(record, answers, QUESTIONS)
        detail["takes"] = [t for t in TAKE_NAMES
                           if (recording_dir / f"{session}_{t}.wav").exists()]
        return detail

    @app.get("/api/audio")
    def session_audio(subject: str, session: str, take: str) -> FileResponse:
        """A saved take, played back on this machine only."""
        subject, session, _ = _find_session(subject, session)
        if take not in TAKE_NAMES:
            raise HTTPException(status_code=422, detail="unknown take")
        path = data / "recordings" / subject / f"{session}_{take}.wav"
        if not path.exists():
            raise HTTPException(status_code=404, detail="no audio for this take")
        return FileResponse(path, media_type="audio/wav", headers=fresh)

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
