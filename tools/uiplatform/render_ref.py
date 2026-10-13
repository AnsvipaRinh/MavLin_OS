#!/usr/bin/env python3
"""render_ref.py - reference renderer for MavLinOS component records.

Why this exists. A data contract that no code can consume is a wish list. This
is the *executable* reference implementation of the record vocabulary: it draws
a `mavlinos.component/1` record from the token set only, with no GTK, no theme
and no application. If a record cannot be rendered here, it is not an
implementable record - which makes this both (a) the oracle for the pixel-level
tests in tests/uiplatform/test_render_ref.py and (b) the mechanism the visual
regression harness of docs/UI_PLATFORM/06-ACCEPTANCE.md (F.4) builds on.

Supported subset of the record vocabulary (deliberately explicit - anything else
is a hard error, never a silent approximation):

  geometry.variants[].intrinsic      -> canvas size
  geometry.layout[]                  -> named rects (hard error if a part is
                                        referenced by visuals but absent)
  visuals.background[]               -> solid | gradient (linear, angle)
  visuals.border[]                   -> width, style solid|inset|outset, radius
  visuals.shadow[]                   -> token value (offset, blur, alpha)
  visuals.glyph[]                    -> filled circle placeholder + asset note
  visuals.per_state[state]           -> the same vocabulary, merged per C.1.4
  states[] , opacity

Coordinate systems: records are authored bottom-left (AppKit), Cairo is
top-left; this renderer performs the single documented conversion so the record
values stay untouched.

Usage:
    render_ref.py --component docs/UI_PLATFORM/examples/component.button.push.json \
                 --tokens design/tokens/design-tokens.json \
                 --out build/render/button.png [--state pressed] [--scale 2]
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys

import cairo

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import validate as V  # noqa: E402


class RenderError(Exception):
    pass


# --- token access -------------------------------------------------------


def hex_rgb(value):
    value = value.lstrip("#")
    if len(value) != 6:
        raise RenderError("token colour must be #rrggbb, got %r" % value)
    try:
        return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError as exc:
        raise RenderError("bad hex %r" % value) from exc


def token_of(tokens, ref):
    if ref not in tokens:
        raise RenderError("token %r is not defined in the token set - the platform "
                          "must not guess a value" % ref)
    return tokens[ref]


def colour_of(tokens, ref):
    tok = token_of(tokens, ref)
    if tok.get("type") != "color":
        raise RenderError("token %r is not a colour (type=%r)" % (ref, tok.get("type")))
    value = tok.get("value")
    if not isinstance(value, str):
        # variants: blue is the default appearance
        variants = tok.get("variants") or {}
        value = variants.get("blue", "")
    if not isinstance(value, str) or not value.startswith("#"):
        raise RenderError("token %r has no colour value" % ref)
    rgb = hex_rgb(value)
    alpha = tok.get("alpha", 1.0)
    return rgb + (float(alpha),)


# --- geometry -----------------------------------------------------------


def flip_y(rect, height):
    """Record coordinates are bottom-left; Cairo is top-left."""
    return (rect["x"], height - rect["y"] - rect["h"], rect["w"], rect["h"])


# --- drawing ------------------------------------------------------------


def draw_fill(cr, tokens, fill, rect, height):
    kind = fill.get("fill")
    if kind == "none":
        return
    if kind == "solid":
        colour = colour_of(tokens, fill["color"])
        cr.set_source_rgba(*colour)
        cr.rectangle(*flip_y(rect, height))
        cr.fill()
        return
    if kind == "gradient":
        if len(fill.get("stops", [])) < 2:
            raise RenderError("gradient needs two stops")
        x, y, w, h = flip_y(rect, height)
        angle = math.radians(fill.get("angle", 90))
        # angle 90 == vertical, top -> bottom (Mavericks control gradients)
        dx = math.cos(angle) * (h / 2.0) * (w / max(w, 1))
        dy = math.sin(angle) * (h / 2.0)
        grad = cairo.LinearGradient(x + w / 2 - dx, y + h / 2 - dy,
                                    x + w / 2 + dx, y + h / 2 + dy)
        for stop in fill["stops"]:
            grad.add_color_stop_rgba(stop["at"], *colour_of(tokens, stop["color"]))
        cr.set_source(grad)
        cr.rectangle(x, y, w, h)
        cr.fill()
        return
    if kind in ("texture", "asset"):
        # the reference renderer draws no artwork: it records the requirement
        cr.set_source_rgba(0.75, 0.75, 0.8, 0.35)
        cr.rectangle(*flip_y(rect, height))
        cr.fill()
        if os.environ.get("MV_RENDER_VERBOSE"):
            print("note: %s fill drawn as placeholder (asset/texture layer)"
                  % kind, file=sys.stderr)
        return
    raise RenderError("unsupported fill %r" % kind)


def draw_border(cr, tokens, border, rect, height):
    x, y, w, h = flip_y(rect, height)
    radius = border.get("radius", 0) or 0
    inset = (border.get("inset") or 0) + (border.get("width", 1) or 1) / 2.0
    if radius:
        _round_rect(cr, x + inset, y + inset, w - 2 * inset, h - 2 * inset, radius)
    else:
        cr.rectangle(x + inset, y + inset, w - 2 * inset, h - 2 * inset)
    colour = colour_of(tokens, border["color"])
    style = border.get("style", "solid")
    if style in ("inset", "outset"):
        base = colour[:3]
        cr.set_source_rgba(*base, colour[3])
        cr.set_line_width(border.get("width", 1))
        cr.stroke()
    else:
        cr.set_source_rgba(*colour)
        cr.set_line_width(border.get("width", 1))
        cr.stroke()


def _round_rect(cr, x, y, w, h, r):
    r = min(r, w / 2.0, h / 2.0)
    cr.move_to(x + r, y)
    cr.line_to(x + w - r, y)
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.line_to(x + w, y + h - r)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.line_to(x + r, y + h)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.line_to(x, y + r)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def draw_shadow(cr, tokens, shadow, rect, height):
    spec = token_of(tokens, shadow["token"])
    value = spec.get("value") if isinstance(spec.get("value"), dict) else spec
    offset = value.get("offset", [0, 0])
    blur = value.get("blur", 0)
    colour = value.get("color", "#000000")
    alpha = value.get("alpha", 0.3)
    rgb = hex_rgb(colour)
    x, y, w, h = flip_y(rect, height)
    cr.save()
    cr.set_source_rgba(*rgb, alpha)
    cr.rectangle(x + offset[0], y + offset[1], w, h)
    cr.fill()
    if blur:
        # approximate with a translucent band (reference renderer, not a blur engine)
        cr.set_source_rgba(*rgb, alpha / 2)
        cr.rectangle(x + offset[0] - blur / 2, y + offset[1] - blur / 2,
                     w + blur, h + blur)
        cr.fill()
    cr.restore()


def draw_glyph(cr, tokens, glyph, rect, height):
    """Glyph artwork is an ASSET, not a vector the reference renderer ships.

    Drawing a placeholder blob here would corrupt the pixel probes of every
    component (a black dot is not a traffic light), so the reference renderer
    deliberately draws nothing and records the requirement. The artwork layer
    (asset.* records + generators) owns this slot.
    """
    if not glyph.get("token"):
        if os.environ.get("MV_RENDER_VERBOSE"):
            print("note: glyph %r skipped - artwork asset, not reference-drawn"
                  % glyph.get("part"), file=sys.stderr)
        return
    x, y, w, h = flip_y(rect, height)
    colour = colour_of(tokens, glyph["token"])
    cr.set_source_rgba(*colour)
    cx, cy, r = x + w / 2.0, y + h / 2.0, min(w, h) / 2.0
    cr.arc(cx, cy, r, 0, 2 * math.pi)
    cr.fill()


def draw_text(cr, tokens, typography, rect, height, text):
    x, y, w, h = flip_y(rect, height)
    tok = token_of(tokens, typography["role"])
    value = tok.get("value") if isinstance(tok.get("value"), dict) else {}
    size = value.get("size_pt", 11)
    cr.set_font_size(size)
    colour = colour_of(tokens, typography["color"]) if typography.get("color") else (0, 0, 0, 1)
    cr.set_source_rgba(*colour)
    extents = cr.text_extents(text)
    tx = x + (w - extents.width) / 2.0
    ty = y + h / 2.0 + size / 3.0
    cr.move_to(tx, ty)
    cr.show_text(text)


# --- record assembly ----------------------------------------------------


def merge_state(visuals, state):
    """C.1.4: base + per_state override; lists replace, scalars replace."""
    merged = copy.deepcopy(visuals)
    override = (visuals.get("per_state") or {}).get(state) or {}
    for key, value in override.items():
        if key in ("background", "border", "shadow", "typography"):
            merged[key] = copy.deepcopy(value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def render(record, tokens, state, scale=1.0, text=None, canvas=None):
    errors = V.check_semantic("component", record)
    if errors:
        raise RenderError("record is not contract-valid: %s" % "; ".join(errors[:3]))

    variants = record["geometry"]["variants"]
    variant = variants[0]
    w = int(round(variant["intrinsic"]["w"] * scale))
    h = int(round(variant["intrinsic"]["h"] * scale))
    pad = int(round(8 * scale))
    if canvas:
        w, h = canvas
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w + 2 * pad, h + 2 * pad)
    cr = cairo.Context(surface)
    cr.scale(scale, scale)
    cr.translate(pad, pad)
    cr.set_line_width(1)

    layout = {part["part"]: part["rect"] for part in record.get("geometry", {}).get("layout", [])}
    visuals = merge_state(record["visuals"], state)

    # Render order (C.1.4): the shadow sits BEHIND the component, then the
    # background, then the border, then glyphs, then text. Drawing the shadow
    # after the background composites black over the body - the defect the
    # "button body is light" probe caught.
    if visuals.get("shadow"):
        for shadow in visuals["shadow"]:
            rect = layout.get(shadow.get("slot"), {"x": 0, "y": 0, "w": w, "h": h})
            draw_shadow(cr, tokens, shadow, rect, h)
    if visuals.get("background"):
        for fill in visuals["background"]:
            rect = layout.get(fill.get("slot"), {"x": 0, "y": 0, "w": w, "h": h})
            draw_fill(cr, tokens, fill, rect, h)
    for border in visuals.get("border", []) or []:
        rect = layout.get(border.get("slot"), {"x": 0, "y": 0, "w": w, "h": h})
        draw_border(cr, tokens, border, rect, h)
    for glyph in visuals.get("glyph", []) or []:
        if "rect" in glyph:
            draw_glyph(cr, tokens, glyph, glyph["rect"], h)
    if visuals.get("typography"):
        rect = layout.get("label", {"x": 0, "y": 0, "w": w, "h": h})
        draw_text(cr, tokens, visuals["typography"][0], rect, h, text or "Button")
    return surface


def surface_to_png(surface):
    import io
    buf = io.BytesIO()
    surface.write_to_png(buf)
    return buf.getvalue()


def load_record(path, tokens_path):
    record = json.load(open(path))
    kind = V.schema_kind_of(record)
    if kind != "component":
        raise RenderError("%s is a %r record, not a component" % (path, kind))
    schemas = V.load_schemas()
    errors = V.validate(record, schemas["component"], schemas["component"], "$", roots=schemas)
    if errors:
        raise RenderError("record does not validate: %s" % "; ".join(errors[:3]))
    tokens = json.load(open(tokens_path)).get("tokens", {})
    return record, tokens


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--component", required=True)
    ap.add_argument("--tokens", default=os.path.join(REPO, "design/tokens/design-tokens.json"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--state", default="normal")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--text", default="Button")
    ap.add_argument("--padding", action="store_true", help="include the focus ring area")
    args = ap.parse_args(argv)

    try:
        record, tokens = load_record(args.component, args.tokens)
        surface = render(record, tokens, args.state, scale=args.scale, text=args.text)
    except (RenderError, OSError, KeyError) as exc:
        print("render FAILED: %s" % exc, file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    surface.write_to_png(args.out)
    print("render OK: %s %s @1x x%.1f -> %s"
          % (record["id"], args.state, args.scale, os.path.relpath(args.out, REPO)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
