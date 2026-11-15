"""The UI must expose the IDs the flow depends on and contain no external calls."""
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def test_record_ids_exist():
    html = (APP / "index.html").read_text(encoding="utf-8")
    for element_id in ("record", "save-session", "take-status", "level-meter",
                       "session-label", "subject", "to-checkin", "passage-text",
                       "take-countdown", "retry-upload", "record-error"):
        assert f'id="{element_id}"' in html, element_id


def test_three_take_flow_is_wired():
    js = (APP / "app.js").read_text(encoding="utf-8")
    for token in ("vowel", "passage", "free", "/api/session", "encodeWav"):
        assert token in js, token


def test_checkin_ids_and_labels():
    html = (APP / "index.html").read_text(encoding="utf-8")
    for element_id in ("checkin-form", "checkin-save", "to-report", "pain-check",
                       "pain-where", "sleep-hours", "anything-else"):
        assert f'id="{element_id}"' in html, element_id
    js = (APP / "app.js").read_text(encoding="utf-8")
    for token in ("/api/context", "buildRaw"):
        assert token in js, token


def test_checkin_form_covers_every_question_and_sends_raw_answers():
    # The form is static, so pin it to the CLI's question list: a question
    # added there must get a control here, and the client must build every field.
    from pipeline.checkin_agent import QUESTIONS

    html = (APP / "index.html").read_text(encoding="utf-8")
    js = (APP / "app.js").read_text(encoding="utf-8")
    build = re.search(r"function buildRaw\(\).*?\n}\n", js, re.S)
    assert build, "buildRaw must exist"
    for question in QUESTIONS:
        field = question["field"]
        assert f'data-field="{field}"' in html, field
        assert re.search(rf"\b{field}:", build.group(0)), field

    assert "parseAnswer" not in js, "the client must not reimplement the CLI parser"
    assert re.search(r"raw:\s*buildRaw\(\)", js), "context POST must send raw answers"


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


def test_report_ids_and_renderer():
    html = (APP / "index.html").read_text(encoding="utf-8")
    for element_id in ("report-headline", "report-list", "baseline-note", "report-refresh"):
        assert f'id="{element_id}"' in html, element_id
    js = (APP / "app.js").read_text(encoding="utf-8")
    for token in ("renderReport", "/api/report", "sparkline"):
        assert token in js, token


def test_report_band_contrast_and_text():
    # Structural guard: visible band outline, readable tag, and a textual band meaning.
    css = (APP / "styles.css").read_text(encoding="utf-8")
    band = re.search(r"\.band\s*\{[^}]*\}", css)
    assert band and "stroke" in band.group(0), "band needs a visible outline"
    tag = re.search(r"\.tag\.explained\s*\{[^}]*\}", css)
    assert tag and "--text-secondary" in tag.group(0), "explained tag needs AA contrast"
    js = (APP / "app.js").read_text(encoding="utf-8")
    assert "baseline band" in js


def normalized(text):
    return " ".join(text.split())


def test_fixed_instructions_and_passage_are_embedded():
    html = (APP / "index.html").read_text(encoding="utf-8")
    js = (APP / "app.js").read_text(encoding="utf-8")
    protocol = (APP.parents[1] / "pipeline" / "recording_protocol.md").read_text(
        encoding="utf-8")

    assert ("Take a normal breath and hold 'ah' at a comfortable, steady pitch and "
            "volume until you run out of comfortable breath.") in html
    assert "Describe what you have done since your last check-in." in html

    passage = re.search(r"> Commander's log.*?until tomorrow\.", protocol, re.S)
    assert passage, "passage not found in the recording protocol"
    assert normalized(passage.group(0).replace(">", " ")) in normalized(html)

    assert 'id="take-countdown"' in html
    assert "COUNTDOWN_SECONDS = 3" in js
    take = re.search(r'\{\s*key:\s*"passage".*?\}', js, re.S)
    assert take, "passage take not found"
    seconds = re.search(r"seconds:\s*(\d+)", take.group(0))
    assert seconds and int(seconds.group(1)) >= 30, "passage take must allow the full read"


def test_browser_audio_constraints_are_requested():
    js = (APP / "app.js").read_text(encoding="utf-8")
    for token in ("echoCancellation: false", "noiseSuppression: false",
                  "autoGainControl: false", "channelCount: 1"):
        assert token in js, token


def test_retry_upload_control_exists():
    html = (APP / "index.html").read_text(encoding="utf-8")
    js = (APP / "app.js").read_text(encoding="utf-8")
    assert 'id="retry-upload"' in html
    assert "Retry upload" in html
    for token in ("retryUpload", "state.takes", "/api/session"):
        assert token in js, token


def test_error_status_paths_are_wired():
    js = (APP / "app.js").read_text(encoding="utf-8")
    for token in ("ERROR_COPY", "NotAllowedError", "status === 422", "status === 409",
                  "Retry save", "Press Refresh"):
        assert token in js, token


def test_stable_features_are_rendered():
    js = (APP / "app.js").read_text(encoding="utf-8")
    assert "stable_features" in js
    assert "Stable this session" in js


def test_navigation_and_retake_controls_exist():
    html = (APP / "index.html").read_text(encoding="utf-8")
    js = (APP / "app.js").read_text(encoding="utf-8")
    for element_id in ("nav-record", "nav-report", "save-session", "replace-session",
                       "take-steps", "to-checkin"):
        assert f'id="{element_id}"' in html, element_id
    # Every take card carries its own Record / Retake button.
    for take in ("vowel", "passage", "free"):
        assert f'class="secondary take-button" data-take="{take}"' in html, take
    for token in ("startTake", "saveSession", "openReport", '"replace", "true"'):
        assert token in js, token
    # Recording a take never stores anything: only Save session uploads.
    start = re.search(r"async function startTake\(key\).*?\n}\n", js, re.S)
    assert start and "uploadTakes" not in start.group(0)
