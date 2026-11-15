# Baseline Drift web UI

Run on the habitat machine, offline:

    python -m pip install -r web/requirements.txt
    python -m uvicorn web.server:app --host 127.0.0.1 --port 8765

Open http://127.0.0.1:8765. One page, three states: record, check-in, report.

## Demo checklist

1. Record three takes for mission day 1; confirm the session lands in `web/data/recordings/`.
2. Repeat for days 2–6. Use the same microphone and the same room.
3. Day 3 completes the baseline; the report stays in the baseline state and says
   scoring begins with the next session. Day 4 is the first scored session, but
   the persistence gate requires the same feature to move in the same direction
   for two consecutive scored sessions, so the earliest finding appears on day 5.
4. A cold/cough check-in tags the matching features as accounted for.
5. Disconnect the network and reload; nothing breaks.
6. Confirm no external requests in the browser network panel.

## Tests

    python -m pytest web/tests -v

The end-to-end test generates synthetic sessions, so it proves the wiring without
needing real recordings. Real recordings still matter for the demo.
