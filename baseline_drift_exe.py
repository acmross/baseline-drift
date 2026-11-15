"""
Windows entry point for the packaged Baseline Drift demo.

Starts the local server on 127.0.0.1, opens the default browser once, and
keeps the console window as the stop control. Set BASELINE_DRIFT_NO_BROWSER=1
for an automated smoke test.
"""
import os
import threading
import webbrowser

import uvicorn

from web.server import app

HOST = "127.0.0.1"
PORT = 8765


def main() -> None:
    """Serve until the console window closes; listen on localhost only."""
    if not os.environ.get("BASELINE_DRIFT_NO_BROWSER"):
        threading.Timer(
            1.5, lambda: webbrowser.open(f"http://{HOST}:{PORT}/")
        ).start()
    print(f"Baseline Drift is running at http://{HOST}:{PORT}")
    print("Everything stays on this machine. Close this window to stop the app.")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
