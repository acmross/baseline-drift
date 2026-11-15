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


def test_checkin_ids_and_labels():
    html = (APP / "index.html").read_text(encoding="utf-8")
    for element_id in ("checkin-form", "question-label", "answer",
                       "checkin-next", "checkin-skip", "to-report"):
        assert f'id="{element_id}"' in html, element_id
    js = (APP / "app.js").read_text(encoding="utf-8")
    for token in ("/api/questions", "/api/context", "buildAnswers"):
        assert token in js, token


def test_checkin_flow_completes_and_inverts_setup():
    # Structural guard: the repo has no DOM/JS harness, so pin the data flow in app.js.
    js = (APP / "app.js").read_text(encoding="utf-8")

    skip = re.search(r'getElementById\("checkin-skip"\)\.addEventListener\(.*?\}\);',
                     js, re.S)
    assert skip, "checkin-skip listener not found"
    block = skip.group(0)
    assert "advanceCheckin(null)" in block, "skip must store null"
    assert "finishCheckin()" in block, "skip must finalize the check-in"

    parser = re.search(r'function parseAnswer\(.*?\n\}', js, re.S)
    assert parser, "parseAnswer not found"
    assert re.search(r'"yesno_inverted".*?!\s*value', parser.group(0), re.S), \
        "yesno_inverted must negate the parsed value"


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
