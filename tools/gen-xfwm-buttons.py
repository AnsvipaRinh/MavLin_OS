#!/usr/bin/env python3
"""Generate the Mavericks xfwm4 window-button pixmaps (deterministic).

Why a generator instead of hand-drawn files
------------------------------------------
The button set that shipped in this repository was malformed: every gradient
button declared `chars_per_pixel = 2` while writing single-character colour
keys, and several files had pixel rows of the wrong length.  GdkPixbuf — the
only decoder xfwm4 uses — rejected them ("Failed to parse <Colors> section"),
so the title bars had no working close/minimise/zoom buttons at all.  Hand
fixing 40 files is how they got broken in the first place; a generator with
four colours per file and no ambiguity cannot drift.

Run:  python3 tools/gen-xfwm-buttons.py           # rewrite the assets
      python3 tools/gen-xfwm-buttons.py --check   # verify they are up to date

Design (Mavericks 10.9):
  * 14x14, 1px transparent margin, circle radius 6
  * vertical gradient: lighter at the top, deeper at the bottom (the glassy
    dome macOS drew on these buttons)
  * a white glyph: X (close), minus (minimise), plus (zoom)
  * inactive: pale grey disc with a grey glyph, exactly as macOS drew
    unfocused window buttons
  * colours are the real 10.9 traffic-light values, the same ones the
    theme's already-valid close.xpm/minimize.xpm used:
    close #ff5f57, minimise #febc2e, zoom #28c840

Only the standard library is used so the result is byte-for-byte reproducible.
"""
import os
import sys

SIZE = 14
# GdkPixbuf's current XPM decoder (the glycin loader shipped with
# gdk-pixbuf 2.44.x) refuses any palette with more than 8 entries, including
# the transparent one.  Measured: 8 colour entries load, 9 fail with
# "Invalid color".  Keep the ramp short so the budget has headroom.
MAX_COLOURS = 8
OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "packages/mavericks-theme/src/mavericks-theme/xfwm4")

CLOSE = (0xff, 0x5f, 0x57)
HIDE = (0xfe, 0xbc, 0x2e)
MAXIMIZE = (0x28, 0xc8, 0x40)
MENU = (0x8e, 0x8e, 0x86)
SHADE = (0x6f, 0x8f, 0xbf)
STICK = (0xb4, 0x8a, 0x3c)
# macOS 10.9 unfocused buttons: a pale grey disc, grey glyph.
INACTIVE = (0xbd, 0xbd, 0xb7)
INACTIVE_GLYPH = (0x8f, 0x8f, 0x8a)
GLYPH = (0xff, 0xff, 0xff)

GRADIENT_STEPS = 5


def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def shift(colour, factor):
    if factor >= 1.0:
        return tuple(min(255, int(round(c + (255 - c) * (factor - 1.0)))) for c in colour)
    return tuple(max(0, int(round(c * factor))) for c in colour)


def disc(x, y, cx=6.5, cy=6.5, r=6.0):
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def glyph_pixels(kind):
    """Set of (x, y) cells covered by the button's symbol."""
    px = set()
    if kind == "close":
        for i in range(3, 11):
            px.add((i, i))
            px.add((13 - i, i))
    elif kind == "hide":
        for x in range(4, 11):
            px.add((x, 7))
    elif kind == "maximize":
        for x in range(4, 11):
            px.add((x, 7))
        for y in range(4, 11):
            px.add((7, y))
    elif kind == "menu":
        for y in range(5, 10):
            for x in range(4, 11):
                px.add((x, y))
    elif kind == "shade":
        for x in range(4, 11):
            px.add((x, 5))
        for x in range(4, 11):
            px.add((x, 9))
    elif kind == "stick":
        for x in range(4, 11):
            px.add((x, 4))
            px.add((x, 10))
        for y in range(4, 11):
            px.add((4, y))
            px.add((10, y))
    elif kind == "none":
        pass
    else:
        raise ValueError(kind)
    return px


def render(kind, base, glyph_colour, glyph_on=True):
    """Return a SIZE x SIZE list of (r, g, b) or None, painted top-down."""
    rows = []
    symbols = glyph_pixels(kind)
    ramp = [mix(base, shift(base, 0.72), i / (GRADIENT_STEPS - 1.0))
            for i in range(GRADIENT_STEPS)]
    for y in range(SIZE):
        row = []
        for x in range(SIZE):
            if not disc(x, y):
                row.append(None)
                continue
            if glyph_on and (x, y) in symbols:
                row.append(glyph_colour)
            else:
                idx = min(GRADIENT_STEPS - 1, max(0, y * GRADIENT_STEPS // SIZE))
                row.append(ramp[idx])
        rows.append(row)
    return rows


# Characters for the XPM palette.  Deliberately NOT the space character: one
# broken file in this theme used a space as a colour key and both GdkPixbuf
# loaders (legacy-xpm and glycin) choked on it.  '.' and 'o' are the classic
# transparent/glyph pair and are unambiguous in every parser.
KEYS = "0123456789abcdefghijklmnopqrstuv"


def to_xpm(rows, name):
    """Serialise to XPM C source with one character per pixel.

    Two shapes matter, and both are dictated by what GdkPixbuf accepts rather
    than by taste:
      * ``static char * name_xpm[]`` — a space after the ``*``, as every
        distro-shipped xfwm4 pixmap is written;
      * the closing ``};`` glued to the last array element on the same line.
        With ``};`` on its own line glycin reports "Failed to parse array end"
        and the file silently loses the button.
    """
    colours = []          # (key, "#rrggbb" or None) in insertion order
    index = {}

    def key_for(rgb):
        if rgb is None:
            if "." not in index:
                index["."] = len(colours)
                colours.append((".", "None"))
            return "."
        token = "#%02x%02x%02x" % rgb
        for k, v in colours:
            if v == token:
                return k
        k = KEYS[len(colours) % len(KEYS)]
        while k in index:
            k = KEYS[(KEYS.index(k) + 1) % len(KEYS)]
        index[k] = len(colours)
        colours.append((k, token))
        return k

    pixels = [[key_for(rgb) for rgb in row] for row in rows]
    height = len(rows)
    width = len(rows[0]) if rows else 0
    # The C identifier must be a real identifier: GdkPixbuf's loaders match the
    # declaration with an identifier pattern, and a hyphen makes them bail with
    # "Failed to parse array end" (the shipped files got this right by using
    # close_active_xpm).
    ident = name.replace("-", "_")
    lines = ["/* XPM */",
             "static char * %s_xpm[] = {" % ident,
             '"%d %d %d 1",' % (width, height, len(colours))]
    for k, v in colours:
        lines.append('"%s c %s",' % (k, v))
    if len(colours) > MAX_COLOURS:
        raise ValueError("%s needs %d palette entries, the XPM decoder caps "
                         "them at %d" % (name, len(colours), MAX_COLOURS))
    for row in pixels:
        lines.append('"%s",' % "".join(row))
    # Last element and the closing brace share a line (see docstring).
    lines[-1] = lines[-1].rstrip(",") + "};"
    return "\n".join(lines) + "\n"


def button(kind, colour, state):
    """state: active | inactive | prelight | pressed"""
    if state == "inactive":
        return render(kind, INACTIVE, INACTIVE_GLYPH)
    if state == "prelight":
        return render(kind, shift(colour, 1.10), GLYPH)
    if state == "pressed":
        return render(kind, shift(colour, 0.82), mix(GLYPH, (0xee, 0xee, 0xee), 0.6))
    return render(kind, colour, GLYPH)


# name, glyph kind, base colour, has toggled variant
BUTTONS = [
    ("close", "close", CLOSE, False),
    ("hide", "hide", HIDE, False),
    ("maximize", "maximize", MAXIMIZE, True),
    ("menu", "menu", MENU, False),
    ("shade", "shade", SHADE, True),
    ("stick", "stick", STICK, True),
]
STATES = ["active", "inactive", "prelight", "pressed"]
TOGGLED_STATES = ["active", "inactive", "prelight", "pressed"]


def wanted():
    out = {}
    for name, kind, colour, toggled in BUTTONS:
        for state in STATES:
            out["%s-%s.xpm" % (name, state)] = (kind, colour, state)
            if toggled:
                out["%s-toggled-%s.xpm" % (name, state)] = (kind, colour, state)
    return out


def generate():
    return dict((fname, to_xpm(button(*args), fname[:-4]))
                for fname, args in wanted().items())


def main(argv):
    check = "--check" in argv
    files = generate()
    bad = []
    for fname, text in sorted(files.items()):
        path = os.path.join(OUT, fname)
        current = None
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                current = fh.read()
        if current == text:
            continue
        if check:
            bad.append(fname)
            continue
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("wrote %s" % fname)
    if check:
        if bad:
            print("FAIL - stale generated assets: %s" % " ".join(sorted(bad)))
            return 1
        print("ok - %d generated button assets are up to date" % len(files))
        return 0
    print("ok - %d button assets written to %s" % (len(files), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))