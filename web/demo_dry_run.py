"""
Baseline Drift demo dry run.

Seeds one synthetic crew member through the live local API, prints the
baseline and findings states, and captures the one-page UI to docs/demo/.
The synthetic audio is a source-model buzz, not speech: this proves the demo
wiring and the report states, not acoustic validity. Real recordings remain
the demo data.

Usage:
    python -m uvicorn web.server:app --host 127.0.0.1 --port 8765
    python web/demo_dry_run.py --reset --capture
"""
import argparse
import shutil
import sys
import tempfile
from pathlib import Path

import httpx
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.make_test_audio import utterance  # noqa: E402

SUBJECT = "AMANDA"

# Same values as the pipeline's synthetic fixture: three baseline sessions,
# then a sustained drop in pitch, loudness and voice quality with more pausing.
PLAN = [
    ("day1", 118, 0.80, 0.010, 0.15),
    ("day2", 121, 0.82, 0.011, 0.17),
    ("day3", 119, 0.79, 0.010, 0.14),
    ("day4", 104, 0.55, 0.019, 0.42),
    ("day5", 102, 0.52, 0.021, 0.45),
    ("day6", 105, 0.54, 0.020, 0.40),
]

# A reported cold accounts for pitch, loudness and voice quality. Normal sleep
# and an unchanged setup leave pausing and speaking rate unexplained, which is
# the report's whole point: show what moved without a mundane explanation.
RAW_DAY6 = {
    "cold_or_congestion": "yeah a bit stuffy",
    "cough": "no",
    "sleep_hours": "7",
    "headache": "no",
    "posture": "sitting",
    "setup_changed": "yes",
    "anything_else": "demo dry run",
}


def wait_for_server(client: httpx.Client, base_url: str) -> None:
    """Fail with a useful message instead of a stack trace when the server is down."""
    try:
        response = client.get(f"{base_url}/api/health")
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - this is the user-facing check
        raise SystemExit(
            f"Local server is not reachable at {base_url}. Start it with:\n"
            "  python -m uvicorn web.server:app --host 127.0.0.1 --port 8765"
        ) from exc


def seed_session(client: httpx.Client, session: str, wav_path: Path) -> None:
    """Post one synthetic session. The same take stands in for all three tasks."""
    blob = wav_path.read_bytes()
    files = {
        "vowel": (f"{session}_vowel.wav", blob, "audio/wav"),
        "passage": (f"{session}_passage.wav", blob, "audio/wav"),
        "free": (f"{session}_free.wav", blob, "audio/wav"),
    }
    response = client.post(
        "/api/session",
        data={"subject": SUBJECT, "session": session},
        files=files,
    )
    if response.status_code == 409:
        print(f"  {session}: already recorded, keeping it")
        return
    response.raise_for_status()
    print(f"  {session}: stored")


def summarize(client: httpx.Client) -> dict:
    """Print the report state the UI will render and return the payload."""
    report = client.get("/api/report", params={"subject": SUBJECT}).json()
    print(f"  state={report['state']}  headline={report['headline']}")
    for finding in report["findings"]:
        explanation = ", ".join(finding["explained"]) or "no reported explanation"
        print(f"    - {finding['label']}: {finding['phrase']} ({explanation})")
    return report


def capture_record(base_url: str, out_path: Path) -> None:
    """Screenshot the record screen and prove the page makes no external requests."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1366, "height": 950})
        requests: list[str] = []
        page.on("request", lambda request: requests.append(request.url))
        page.goto(f"{base_url}/", wait_until="networkidle")
        page.screenshot(path=str(out_path), full_page=True)
        browser.close()

    external = [url for url in requests if not _is_local(url, base_url)]
    print(f"  record screen -> {out_path}")
    _assert_offline(external)


def capture_report(base_url: str, out_path: Path) -> str:
    """Open the page, switch to the report state, wait for content, then screenshot."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1366, "height": 950})
        requests: list[str] = []
        page.on("request", lambda request: requests.append(request.url))
        page.goto(f"{base_url}/", wait_until="networkidle")
        page.evaluate(
            "state.subject='AMANDA';"
            "document.getElementById('subject').value='AMANDA';"
            "showState('report'); loadReport();"
        )
        page.wait_for_function(
            "document.querySelector('#report-headline')"
            " && document.querySelector('#report-headline').textContent.length > 0"
        )
        page.wait_for_function(
            "document.querySelector('#report-list')"
            " && document.querySelector('#report-list').children.length > 0"
        )
        page.wait_for_timeout(300)
        page.screenshot(path=str(out_path), full_page=True)
        headline = page.text_content("#report-headline") or ""
        browser.close()

    external = [url for url in requests if not _is_local(url, base_url)]
    print(f"  report -> {out_path}  ({headline.strip()})")
    _assert_offline(external)
    return headline


def _is_local(url: str, base_url: str) -> bool:
    """A page request is local if it targets the app or is an in-memory asset."""
    return url.startswith(base_url) or url.startswith(("data:", "blob:"))


def _assert_offline(external: list[str]) -> None:
    """The no-network premise is a demo claim, so fail the run if it is broken."""
    if external:
        raise SystemExit("External requests found: " + ", ".join(sorted(set(external))))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--reset", action="store_true",
                        help="delete web/data before seeding (demo data only)")
    parser.add_argument("--capture", action="store_true",
                        help="screenshot the UI with Playwright")
    args = parser.parse_args()

    if args.reset:
        data_dir = ROOT / "web" / "data"
        shutil.rmtree(data_dir, ignore_errors=True)
        print(f"Reset {data_dir}")

    shots = ROOT / "docs" / "demo"
    shots.mkdir(parents=True, exist_ok=True)

    with httpx.Client(base_url=args.base_url, timeout=120) as client:
        wait_for_server(client, args.base_url)

        if args.capture:
            capture_record(args.base_url, shots / "record.png")

        print("Seeding baseline sessions 1-3")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for session, f0, amp, jitter, pause in PLAN[:3]:
                wav = tmp_path / f"{session}.wav"
                sf.write(wav, utterance(f0, amp, jitter, pause), 16000)
                seed_session(client, session, wav)
            print("Baseline state")
            summarize(client)
            if args.capture:
                capture_report(args.base_url, shots / "report-baseline.png")

            print("Seeding drifting sessions 4-6")
            for session, f0, amp, jitter, pause in PLAN[3:]:
                wav = tmp_path / f"{session}.wav"
                sf.write(wav, utterance(f0, amp, jitter, pause), 16000)
                seed_session(client, session, wav)

        context = client.post(
            "/api/context",
            json={"subject": SUBJECT, "session": "day6", "raw": RAW_DAY6},
        )
        context.raise_for_status()
        print("Day 6 check-in stored (cold reported, normal sleep, same setup)")

        print("Findings state")
        summarize(client)
        if args.capture:
            capture_report(args.base_url, shots / "report-findings.png")

    print("Demo dry run complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
