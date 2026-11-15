"""
Build the online preview: the same page as the app, with no pipeline behind it.

The preview opens on the sample report (see make_sample.py) and lets a visitor
explore the Report and Trends views in a browser with nothing to install. A
visitor can also go through recording and the check-in: the audio stays in
their browser tab and is not measured, because measuring a voice needs the
local pipeline, and the page says so. If web/app/real_report.json exists (see
make_real_report.py) it is offered as a second, real dataset. Output goes to
docs/try/, which GitHub Pages can serve.

Usage:
    python web/build_static_demo.py [output_dir]
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "web" / "app"
REPO_URL = "https://github.com/acmross/baseline-drift"

NOTE = f'''    <aside class="privacy" aria-label="About this preview">
      <p class="privacy-title">Try the check-in here. Your voice is not measured or kept.</p>
      <p>You can record the three takes, play them back and fill in the check-in. The audio never leaves this browser tab and is discarded. Measuring a voice needs Baseline Drift running on your own computer, which is also what keeps recordings private, so the report you see afterwards is the sample. To measure your own voice, follow the steps at <a href="{REPO_URL}#try-it">{REPO_URL}</a>.</p>
    </aside>
'''


def build(out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    for name in ("app.js", "styles.css", "sample_report.json"):
        shutil.copyfile(APP / name, out / name)
    real = APP / "real_report.json"
    if real.exists():
        shutil.copyfile(real, out / real.name)
    html = (APP / "index.html").read_text(encoding="utf-8")
    replacements = [
        ('href="/styles.css"', 'href="styles.css"'),
        ('<script src="/app.js"></script>',
         '<script>window.BASELINE_DRIFT_STATIC = true;</script>\n<script src="app.js"></script>'),
        ('    <h2 id="record-title">Record</h2>\n',
         '    <h2 id="record-title">Record</h2>\n' + NOTE),
    ]
    for old, new in replacements:
        if html.count(old) != 1:
            raise SystemExit(f"expected exactly one {old!r} in index.html")
        html = html.replace(old, new)
    (out / "index.html").write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "try"
    print(f"wrote {build(target)}")
