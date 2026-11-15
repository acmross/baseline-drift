"""Compute WCAG contrast from the tokens the shipped stylesheet actually uses.

The numbers are derived here rather than copied, so a future palette edit either
keeps the AA/3:1 guarantees or fails the test.
"""
import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "app" / "styles.css").read_text(
    encoding="utf-8")


def root_tokens():
    root = re.search(r":root\s*\{([^}]*)\}", CSS, re.S)
    assert root, "styles.css has no :root block"
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", root.group(1)))


def block(selector):
    match = re.search(rf"(?m)^{re.escape(selector)}\s*\{{([^}}]*)\}}", CSS)
    assert match, f"{selector} rule not found"
    return match.group(1)


def rgb(hex_value):
    value = hex_value.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return tuple(int(value[index:index + 2], 16) / 255 for index in (0, 2, 4))


def linear(channel):
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def luminance(hex_value):
    red, green, blue = rgb(hex_value)
    return (0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue))


def contrast(first, second):
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def test_button_text_meets_aa():
    tokens = root_tokens()
    rule = block("button")
    background = re.search(r"background:\s*var\(--([\w-]+)\)", rule)
    text = re.search(r"color:\s*(#[0-9a-fA-F]{3,6})", rule)
    assert background and text, "button must declare token background and text color"
    assert contrast(text.group(1), tokens[background.group(1)]) >= 4.5


def test_input_border_meets_non_text_contrast():
    tokens = root_tokens()
    rule = block("input")
    background = re.search(r"background:\s*var\(--([\w-]+)\)", rule)
    border = re.search(r"border:\s*1px solid var\(--([\w-]+)\)", rule)
    assert background and border, "input must declare token background and border"
    assert contrast(tokens[border.group(1)], tokens[background.group(1)]) >= 3.0
