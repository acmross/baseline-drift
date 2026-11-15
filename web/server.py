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
