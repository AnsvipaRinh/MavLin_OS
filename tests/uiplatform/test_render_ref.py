#!/usr/bin/env python3
"""Tests for the reference renderer (tools/uiplatform/render_ref.py).

This is the executable half of the contract: it proves that the example records
are *drawable* from the token set alone, that the declared states actually
change the pixels, and that the renderer refuses to draw when the record or the
token set is broken (a renderer that silently guesses is what made the theme
drift in the first place).

Pixel probes use the record's own geometry, so a failure means either the
record or the renderer is wrong - both are the point.
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools", "uiplatform"))

import render_ref as R  # noqa: E402
from PIL import Image  # noqa: E402

EXAMPLES = os.path.join(REPO, "docs", "UI_PLATFORM", "examples")
TOKENS = os.path.join(REPO, "design", "tokens", "design-tokens.json")

FAILURES = []
CHECKS = [0]


def check(name, condition, detail=""):
    CHECKS[0] += 1
    if condition:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        FAILURES.append(name)


def pixels(surface):
    """-> (PIL image, scale-independent getter)"""
    png = R.surface_to_png(surface)
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    return img, img.getpixel


def load(record_name):
    return R.load_record(os.path.join(EXAMPLES, record_name), TOKENS)


def centre(record, part):
    """Record-space centre of a layout part, converted to surface pixels."""
    rect = [p["rect"] for p in record["geometry"]["layout"] if p["part"] == part][0]
    height = record["geometry"]["variants"][0]["intrinsic"]["h"]
    x = rect["x"] + rect["w"] / 2.0 + R_PAD
    y = (height - rect["y"] - rect["h"] / 2.0) + R_PAD
    return x, y


R_PAD = 8


def test_button_renders_from_tokens():
    record, tokens = load("component.button.push.json")
    surface = R.render(record, tokens, "normal", text="Save")
    img, getpixel = pixels(surface)
    check("button surface size = intrinsic + padding",
          img.size == (int(68 + 2 * R_PAD), int(22 + 2 * R_PAD)), img.size)

    # top and bottom of the bevel must differ (a gradient was drawn). Probe
    # well inside the frame: y+2 is the border stroke, not the body.
    top = getpixel((R_PAD + 34, R_PAD + 9))
    bottom = getpixel((R_PAD + 34, R_PAD + 15))
    check("button draws a gradient (top != bottom)", top != bottom, (top, bottom))
    check("button body is light", min(top[:3]) > 180, top)


def test_states_change_pixels():
    record, tokens = load("component.button.push.json")
    states = {}
    for state in ("normal", "hover", "pressed", "disabled", "inactive-window"):
        _img, getpixel = pixels(R.render(record, tokens, state))
        states[state] = getpixel((R_PAD + 34, R_PAD + 2))
    check("normal and pressed differ",
          states["normal"] != states["pressed"],
          (states["normal"], states["pressed"]))
    check("hover differs from normal", states["hover"] != states["normal"])
    distinct = {v for v in states.values()}
    check("declared states are visually distinct", len(distinct) >= 3,
          "%d distinct of %d states" % (len(distinct), len(states)))


def test_renderer_refuses_missing_token():
    record, tokens = load("component.button.push.json")
    broken = dict(tokens)
    broken.pop("color.control.background.top", None)
    try:
        R.render(record, broken, "normal")
        check("missing token is a hard error", False, "render succeeded")
    except R.RenderError as exc:
        check("missing token is a hard error", "not defined" in str(exc), str(exc))


def test_renderer_refuses_invalid_record():
    record, tokens = load("component.button.push.json")
    broken = dict(record)
    broken["states"] = []            # schema: minItems 1
    try:
        R.render(broken, tokens, "normal")
        check("invalid record is rejected", False, "render succeeded")
    except R.RenderError as exc:
        check("invalid record is rejected", "not contract-valid" in str(exc), str(exc))


def test_traffic_lights_states():
    record, tokens = load("component.window.traffic-lights.json")

    _img, getpixel = pixels(R.render(record, tokens, "normal"))
    close = getpixel(centre(record, "close"))
    mini = getpixel(centre(record, "miniaturize"))
    zoom = getpixel(centre(record, "zoom"))
    check("traffic lights are three different colours", close != mini != zoom,
          (close, mini, zoom))
    check("close light is red-dominant", close[0] > close[1] and close[0] > close[2], close)
    check("minimize light is yellow-dominant",
          mini[0] > mini[2] and mini[1] > mini[2], mini)
    check("zoom light is green-dominant", zoom[1] > zoom[0] and zoom[1] > zoom[2], zoom)

    _img, getpixel_inactive = pixels(R.render(record, tokens, "inactive-window"))
    i_close = getpixel_inactive(centre(record, "close"))
    i_mini = getpixel_inactive(centre(record, "miniaturize"))
    i_zoom = getpixel_inactive(centre(record, "zoom"))
    check("inactive window greys all three lights",
          i_close == i_mini == i_zoom, (i_close, i_mini, i_zoom))
    check("inactive grey differs from the active colour",
          i_close != close, (i_close, close))


def test_scale_is_linear():
    record, tokens = load("component.button.push.json")
    img1, _ = pixels(R.render(record, tokens, "normal", scale=1.0))
    img2, _ = pixels(R.render(record, tokens, "normal", scale=2.0))
    check("2x rendering doubles the canvas", img2.size == (img1.size[0] * 2, img1.size[1] * 2),
          (img1.size, img2.size))


def test_dependency_closure():
    """R-TOKENDEP: the records' token references must exist in the token set."""
    import validate as V
    result = V.check_deps([os.path.join(EXAMPLES, f) for f in os.listdir(EXAMPLES)
                           if f.endswith(".json")], TOKENS)
    check("every token referenced by the examples is defined", result["ok"],
          "; ".join(result["errors"][:3]))
    check("dependency check saw all example records", result["records"] >= 6,
          "%d records" % result["records"])


def main():
    for fn in sorted(globals()):
        if fn.startswith("test_"):
            globals()[fn]()
    print("\nreference renderer: %d checks, %d failed" % (CHECKS[0], len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
