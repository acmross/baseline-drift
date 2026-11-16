"""
Put a fresh export of the slide deck into the repo.

The deck is edited in Claude and exported from there as a web page (Download,
"Web page (.html)"). The export copies every style on the page, including any
hide-rules a browser ad blocker injected, which adds a long list of ad and
adult site names to the file. This strips those rules and nothing else, then
writes docs/pitch-deck.html, the public address the submission links to.

Usage:
    python tools/clean_deck.py "path/to/Baseline Drift.html"
"""
import re
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent / "docs" / "pitch-deck.html"


def strip_blocker_rules(css: str) -> tuple[str, int]:
    """Drop top-level rules that are ad-blocker hide lists: a very long
    selector list whose block only hides things."""
    out, i, dropped = [], 0, 0
    while i < len(css):
        j = css.find("{", i)
        if j < 0:
            out.append(css[i:])
            break
        depth, k = 1, j + 1
        while k < len(css) and depth:
            depth += {"{": 1, "}": -1}.get(css[k], 0)
            k += 1
        selector, block = css[i:j], css[j:k]
        hides = ("display: none !important" in block
                 and "visibility: hidden !important" in block)
        if not selector.lstrip().startswith("@") and hides and len(selector) > 1500:
            dropped += 1
        else:
            out.append(selector + block)
        i = k
    return "".join(out), dropped


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    html = Path(sys.argv[1]).read_text(encoding="utf-8")
    total = 0

    def clean(match: re.Match) -> str:
        nonlocal total
        css, dropped = strip_blocker_rules(match.group(2))
        total += dropped
        return match.group(1) + css + match.group(3)

    html = re.sub(r"(<style[^>]*>)(.*?)(</style>)", clean, html, flags=re.S)
    slides = len(re.findall(r'<section class="deck-slide"', html))
    if slides != 7:
        print(f"expected 7 slides, found {slides}; not writing")
        return 1
    TARGET.write_text(html, encoding="utf-8")
    print(f"wrote {TARGET.name}: {slides} slides, {total} ad-blocker rules removed, "
          f"{len(html) // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
