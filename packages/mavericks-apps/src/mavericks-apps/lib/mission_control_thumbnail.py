#!/usr/bin/env python3
"""Mission Control thumbnail capture — two complementary backends.

1. `capture_window(win_id, max_size)` — one-shot, read-only capture of a
   mapped X11 window via XCompositeNameWindowPixmap (no manual redirection)
   and XGetImage, converted to a GdkPixbuf RGB image. This is the path the
   GTK overview (mv-mc-overview) renders with.

2. `ThumbnailCapture` — live-capture backend via direct ctypes bindings to
   libX11 + libXcomposite + libXdamage + libXfixes: manual redirect +
   NameWindowPixmap + XGetImage producing raw RGBA bytes (no GTK/pixbuf
   dependency in that layer), plus XDamage/XFixes damage tracking
   (start_capture/poll_damage/stop_capture) and a deterministic placeholder
   fallback. Used for damage-tracked recapture and headless pipelines.

Shared window-id parsing comes from mission_control._parse_window_id.
"""
import ctypes
import ctypes.util
import os
import select
from typing import Any, Dict, List, Optional, Tuple

from mission_control import _parse_window_id

_ZPIXMAP = 2

class _XWindowAttributes(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_int), ("y", ctypes.c_int), ("width", ctypes.c_int),
        ("height", ctypes.c_int), ("border_width", ctypes.c_int),
        ("depth", ctypes.c_int), ("visual", ctypes.c_void_p),
        ("root", ctypes.c_ulong), ("class_", ctypes.c_int),
        ("bit_gravity", ctypes.c_int), ("win_gravity", ctypes.c_int),
        ("backing_store", ctypes.c_int), ("backing_planes", ctypes.c_ulong),
        ("backing_pixel", ctypes.c_ulong), ("save_under", ctypes.c_int),
        ("colormap", ctypes.c_ulong), ("map_installed", ctypes.c_int),
        ("map_state", ctypes.c_int), ("all_event_masks", ctypes.c_long),
        ("your_event_mask", ctypes.c_long), ("do_not_propagate_mask", ctypes.c_long),
        ("override_redirect", ctypes.c_int), ("screen", ctypes.c_void_p),
    ]

class _XImage(ctypes.Structure):
    _fields_ = [
        ("width", ctypes.c_int), ("height", ctypes.c_int), ("xoffset", ctypes.c_int),
        ("format", ctypes.c_int), ("data", ctypes.POINTER(ctypes.c_ubyte)),
        ("byte_order", ctypes.c_int), ("bitmap_unit", ctypes.c_int),
        ("bitmap_bit_order", ctypes.c_int), ("bitmap_pad", ctypes.c_int),
        ("depth", ctypes.c_int), ("bytes_per_line", ctypes.c_int),
        ("bits_per_pixel", ctypes.c_int), ("red_mask", ctypes.c_ulong),
        ("green_mask", ctypes.c_ulong), ("blue_mask", ctypes.c_ulong),
        ("obdata", ctypes.c_void_p),
    ]

def _load_x11():
    path = ctypes.util.find_library("X11")
    if not path:
        raise RuntimeError("libX11 is not available")
    lib = ctypes.CDLL(path)
    lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
    lib.XOpenDisplay.restype = ctypes.c_void_p
    lib.XCloseDisplay.argtypes = [ctypes.c_void_p]
    lib.XGetWindowAttributes.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(_XWindowAttributes)]
    lib.XGetWindowAttributes.restype = ctypes.c_int
    lib.XGetImage.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_ulong, ctypes.c_int]
    lib.XGetImage.restype = ctypes.POINTER(_XImage)
    lib.XDestroyImage.argtypes = [ctypes.POINTER(_XImage)]
    lib.XDestroyImage.restype = ctypes.c_int
    lib.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
    return lib

def _load_xcomposite():
    path = ctypes.util.find_library("Xcomposite")
    if not path:
        raise RuntimeError("libXcomposite is not available")
    lib = ctypes.CDLL(path)
    lib.XCompositeQueryExtension.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    lib.XCompositeQueryExtension.restype = ctypes.c_int
    lib.XCompositeNameWindowPixmap.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    lib.XCompositeNameWindowPixmap.restype = ctypes.c_ulong
    return lib

def _mask_shift(mask: int) -> Tuple[int, int]:
    if not mask:
        return 0, 0
    shift = 0
    while ((mask >> shift) & 1) == 0:
        shift += 1
    bits = 0
    value = mask >> shift
    while value & 1:
        bits += 1
        value >>= 1
    return shift, bits

def _scale_channel(value: int, bits: int) -> int:
    """Rescale a `bits`-wide channel value to 0..255.

    bits==8 is already the target range — return the value unchanged
    (union-merge fix: the original returned a constant 255 here, failing
    the 32-bit image conversion test).
    """
    if bits <= 0:
        return 0
    maximum = (1 << bits) - 1
    if maximum == 255:
        return value
    return (value * 255 + maximum // 2) // maximum

def _image_to_rgb(image: _XImage) -> bytearray:
    """Convert an XImage to packed RGB888."""
    if image.bits_per_pixel not in (16, 24, 32):
        raise RuntimeError(f"unsupported bits_per_pixel={image.bits_per_pixel}")
    width, height = image.width, image.height
    bpp = (image.bits_per_pixel + 7) // 8
    raw = ctypes.string_at(image.data, image.bytes_per_line * height)
    red_mask, green_mask, blue_mask = int(image.red_mask), int(image.green_mask), int(image.blue_mask)
    if not (red_mask or green_mask or blue_mask):
        # XGetImage on a PIXMAP leaves the channel masks undefined (zeroed
        # on Xorg/Xvfb — verified). Fall back to the standard ZPixmap
        # layouts for the depth; this is what every real server writes.
        if image.bits_per_pixel == 16:
            red_mask, green_mask, blue_mask = 0xF800, 0x07E0, 0x001F
        else:
            red_mask, green_mask, blue_mask = 0xFF0000, 0x00FF00, 0x0000FF
    rshift, rbits = _mask_shift(red_mask)
    gshift, gbits = _mask_shift(green_mask)
    bshift, bbits = _mask_shift(blue_mask)
    endian = "little" if image.byte_order == 0 else "big"
    out = bytearray(width * height * 3)
    pos = 0
    for y in range(height):
        row = y * image.bytes_per_line
        for x in range(width):
            start = row + x * bpp
            pixel = int.from_bytes(raw[start:start + bpp], endian)
            out[pos:pos + 3] = bytes((
                _scale_channel((pixel & red_mask) >> rshift, rbits),
                _scale_channel((pixel & green_mask) >> gshift, gbits),
                _scale_channel((pixel & blue_mask) >> bshift, bbits),
            ))
            pos += 3
    return out

def _pixbuf_from_rgb(data: bytearray, width: int, height: int):
    try:
        from gi.repository import GdkPixbuf
    except ImportError as exc:
        raise RuntimeError("PyGObject/GdkPixbuf is required") from exc
    holder = {"data": data}
    def release(_data):
        holder.clear()
    return GdkPixbuf.Pixbuf.new_from_data(
        holder["data"], GdkPixbuf.Colorspace.RGB, False, 8,
        width, height, width * 3, release, None)

def capture_window(win_id: int, max_size: Optional[Tuple[int, int]] = None):
    """Return a GdkPixbuf for a mapped X11 window, or None on failure.

    Capture is read-only. Minimized/unmapped windows return None.
    """
    try:
        x11, xc = _load_x11(), _load_xcomposite()
    except RuntimeError:
        return None
    display = x11.XOpenDisplay(None)
    if not display:
        return None
    image = None
    try:
        attrs = _XWindowAttributes()
        if not x11.XGetWindowAttributes(display, ctypes.c_ulong(win_id), ctypes.byref(attrs)):
            return None
        if attrs.map_state != 2 or attrs.width <= 0 or attrs.height <= 0:
            return None
        event_base, error_base = ctypes.c_int(), ctypes.c_int()
        if not xc.XCompositeQueryExtension(display, ctypes.byref(event_base), ctypes.byref(error_base)):
            return None
        pixmap = xc.XCompositeNameWindowPixmap(display, ctypes.c_ulong(win_id))
        if not pixmap:
            return None
        x11.XSync(display, 0)
        image = x11.XGetImage(
            display, ctypes.c_ulong(pixmap), 0, 0,
            ctypes.c_uint(attrs.width), ctypes.c_uint(attrs.height),
            ctypes.c_ulong(0xFFFFFFFF), _ZPIXMAP)
        if not image:
            return None
        data = _image_to_rgb(image.contents)
        width, height = image.contents.width, image.contents.height
        pixbuf = _pixbuf_from_rgb(data, width, height)
        if max_size:
            max_w, max_h = max_size
            if max_w > 0 and max_h > 0 and (width > max_w or height > max_h):
                from gi.repository import GdkPixbuf
                scale = min(max_w / width, max_h / height)
                nw, nh = max(1, round(width * scale)), max(1, round(height * scale))
                return pixbuf.scale_simple(nw, nh, GdkPixbuf.InterpType.BILINEAR)
        return pixbuf
    except Exception:
        return None
    finally:
        if image:
            try:
                x11.XDestroyImage(image)
            except Exception:
                pass
        x11.XCloseDisplay(display)


# --- Live-capture backend: XComposite / XDamage / XFixes (ctypes, headless) ---
#
# Mission Control slice 3 (docs/MISSION_CONTROL_PLAN.md O3): capture window
# content as scaled RGBA thumbnails for the overview grid.
#
# Backend: direct ctypes bindings to libX11 + libXcomposite + libXdamage +
# libXfixes. python-xlib cannot be mixed in here: it speaks the X11 wire
# protocol itself and has no libX11 Display* to hand to XComposite* calls.
# No GTK / Gdk / pixbuf dependency in this layer — capture_window() returns
# raw RGBA bytes + geometry, which the renderer slice wraps.
#
# Headless discipline: opens ONLY the display named by `display_name` or
# $DISPLAY and refuses any display listed in $MV_FORBIDDEN_DISPLAYS (the
# captured host display — see scripts/gui-isolation.sh). Tests pin this to
# the dedicated Xvfb :97; no host display access ever happens from here.

_X11_LIB_NAMES = ("libX11.so.6", "libX11.so")
_XCOMPOSITE_LIB_NAMES = ("libXcomposite.so.1", "libXcomposite.so")
_XDAMAGE_LIB_NAMES = ("libXdamage.so.1", "libXdamage.so")
_XFIXES_LIB_NAMES = ("libXfixes.so.3", "libXfixes.so")

CompositeRedirectAutomatic = 0
ZPixmap = 2
AllPlanes = 0xFFFFFFFF
LSBFirst = 0
XDamageReportNonEmpty = 0
XDamageNotify = 0


class _XRectangle(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_short),
        ("y", ctypes.c_short),
        ("width", ctypes.c_short),
        ("height", ctypes.c_short),
    ]


class _XDamageNotifyEvent(ctypes.Structure):
    """Mirrors XDamageNotifyEvent from Xdamage.h (ctypes handles alignment)."""
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("drawable", ctypes.c_ulong),
        ("damage", ctypes.c_ulong),
        ("level", ctypes.c_int),
        ("more", ctypes.c_int),
        ("timestamp", ctypes.c_ulong),
        ("area", _XRectangle),
        ("geometry", _XRectangle),
    ]


def _load_first_ctypes(names):
    """Load the first loadable library from `names`; None if all fail."""
    for name in names:
        try:
            return ctypes.CDLL(name)
        except OSError:
            continue
    return None


def _bind_ctypes(lib, name, restype, argtypes):
    """Get callable `name` from `lib`, best-effort setting its ctypes signature.

    Signature assignment is wrapped so unit tests can inject plain fake
    callables instead of real CDLL function objects.
    """
    fn = getattr(lib, name, None)
    if fn is None:
        return None
    try:
        fn.restype = restype
        fn.argtypes = argtypes
    except Exception:
        pass
    return fn


def fit_dimensions(src_w: int, src_h: int, max_w: int, max_h: int) -> Tuple[int, int]:
    """Scale (src_w, src_h) to fit inside (max_w, max_h), preserving aspect.

    Pure function. Upscaling allowed (thumbnail fills its grid cell).
    Returns (w, h), both >= 1.
    """
    if src_w <= 0 or src_h <= 0 or max_w <= 0 or max_h <= 0:
        return (1, 1)
    scale = min(max_w / src_w, max_h / src_h)
    return (max(1, int(src_w * scale)), max(1, int(src_h * scale)))


def _bgra_to_rgba(buf: bytes, width: int, height: int, src_stride: int, has_alpha: bool = False) -> bytes:
    """Convert a little-endian 32bpp ZPixmap BGRA/X buffer to packed RGBA.

    Pure function over bytes, vectorized with per-channel slicing (C speed).
    `src_stride` may exceed width*4 (server-side row padding). The 4th byte
    is undefined for depth-24 pixmaps, so alpha is forced opaque unless
    has_alpha (depth 32).
    """
    row_bytes = width * 4
    opaque = b"\xff" * width
    out = bytearray(height * row_bytes)
    for y in range(height):
        src = y * src_stride
        dst = y * row_bytes
        rb = bytes(buf[src:src + row_bytes])
        out[dst:dst + row_bytes:4] = rb[2::4]                      # R
        out[dst + 1:dst + 1 + row_bytes:4] = rb[1::4]              # G
        out[dst + 2:dst + 2 + row_bytes:4] = rb[0::4]              # B
        out[dst + 3:dst + 3 + row_bytes:4] = rb[3::4] if has_alpha else opaque
    return bytes(out)


def _scale_rgba(data: bytes, src_w: int, src_h: int, dst_w: int, dst_h: int) -> bytes:
    """Nearest-neighbour rescale of packed RGBA bytes, vectorized per channel.

    Pure function. Quality is fine for one-shot overview thumbnails; the
    python-level cost is O(rows + dst pixels), everything else is C-speed
    slicing.
    """
    if src_w <= 0 or src_h <= 0 or dst_w <= 0 or dst_h <= 0:
        return b""
    if dst_w == src_w and dst_h == src_h:
        return bytes(data[:src_w * src_h * 4])

    # Split channels once (1 byte per pixel each, row-major).
    channels = [data[o::4] for o in range(4)]

    # Row pick (nearest): join the chosen source rows per channel.
    row_idxs = [min(src_h - 1, ty * src_h // dst_h) for ty in range(dst_h)]
    picked = [b"".join(ch[r * src_w:(r + 1) * src_w] for r in row_idxs) for ch in channels]

    out = bytearray(dst_w * dst_h * 4)
    if src_w == dst_w:
        for ci, ch in enumerate(picked):
            out[ci::4] = ch
    elif src_w % dst_w == 0:
        # Uniform column step: in the picked buffer (dst_h contiguous rows
        # of dst_w*step bytes), the source index of output cell n is
        # exactly n*step — so one strided slice per channel does the job.
        step = src_w // dst_w
        for ci, ch in enumerate(picked):
            out[ci::4] = ch[::step]
    else:
        col_idxs = [tx * src_w // dst_w for tx in range(dst_w)]
        for ci, ch in enumerate(picked):
            parts = []
            for r in range(dst_h):
                base = r * src_w
                row = ch[base:base + src_w]
                parts.append(bytes(map(row.__getitem__, col_idxs)))
            out[ci::4] = b"".join(parts)
    return bytes(out)


def _placeholder_rgba(width: int, height: int, cell: int = 16) -> bytes:
    """Deterministic checkerboard placeholder thumbnail as packed RGBA bytes.

    Vectorized: builds one two-cell row pattern pair and tiles it.
    """
    width = max(1, int(width))
    height = max(1, int(height))
    light = bytes((214, 214, 214, 255))
    dark = bytes((152, 152, 152, 255))
    pair_a = light * cell + dark * cell       # two cells = 2*cell pixels
    pair_b = dark * cell + light * cell
    reps = width // (cell * 2) + 1            # tile the pair across the row
    row_a = (pair_a * reps)[:width * 4]
    row_b = (pair_b * reps)[:width * 4]
    block = row_a * cell + row_b * cell           # 2*cell rows
    full = block * (height // (2 * cell) + 1)
    return full[:width * height * 4]


class ThumbnailCapture:
    """Capture window content as scaled RGBA thumbnails for Mission Control.

    Flow (docs/MISSION_CONTROL_PLAN.md §3.5):
      XCompositeRedirectWindow(Automatic) — keeps off-screen content valid
        (server-side only, invisible to apps and the user; undone in
        stop_capture/close or right after a single-shot capture);
      XCompositeNameWindowPixmap          — get the backing X11 pixmap;
      XGetImage(ZPixmap)                  — read pixels (BGRA -> RGBA);
      fit_dimensions + _scale_rgba        — aspect-preserving cell fit.

    Live updates (start_capture/poll_damage/stop_capture):
      XDamageCreate(NonEmpty) per window + an XFixes region as the damage
      'parts' sink; poll_damage() drains events, returns damaged window ids
      with bounding boxes and invokes the registered callback. Recapturing
      pixels stays the caller's job (capture_window() on the reported ids).

    Fallback: when any library/extension is unavailable or a capture step
    fails (unmapped/minimized window, exotic format), capture_window()
    returns a deterministic checkerboard placeholder instead of raising.

    Headless-only: refuses displays listed in $MV_FORBIDDEN_DISPLAYS; tests
    pin DISPLAY to the dedicated Xvfb :97 via scripts/gui-isolation.sh.
    """

    def __init__(self, display_name: Optional[str] = None, libs: Optional[Dict[str, Any]] = None):
        """Open the display and probe XComposite/XDamage/XFixes.

        Args:
            display_name: X display to open. Defaults to $DISPLAY. Tests pin
                this to Xvfb :97 via gui-isolation.sh.
            libs: optional injected libraries for unit tests, dict with keys
                'x11', 'composite', 'damage', 'fixes' (fake callables).

        Raises:
            RuntimeError: no DISPLAY given, display is forbidden
                ($MV_FORBIDDEN_DISPLAYS), display open failed, or libX11
                itself is unavailable.
        """
        self._display_name = display_name if display_name is not None else os.environ.get("DISPLAY", "")
        self._closed = False
        self._dpy = None
        self._owns_display = False
        self._composite_ok = False
        self._damage_base = -1
        self._fixes_ok = False
        self._redirected = set()      # win ids currently redirected by us
        self._damages = {}            # win id -> Damage XID
        self._parts = {}              # win id -> XserverRegion (damage parts)
        self._callback = None
        self._capturing = False
        self._err_handler = None
        self._prev_err_handler = None

        injected = libs or {}
        self._x11 = injected.get("x11") or _load_first_ctypes(_X11_LIB_NAMES)
        self._xcomposite = injected.get("composite") or _load_first_ctypes(_XCOMPOSITE_LIB_NAMES)
        self._xdamage = injected.get("damage") or _load_first_ctypes(_XDAMAGE_LIB_NAMES)
        self._xfixes = injected.get("fixes") or _load_first_ctypes(_XFIXES_LIB_NAMES)

        if self._x11 is None:
            raise RuntimeError("libX11 unavailable for thumbnail capture")

        if not self._display_name:
            raise RuntimeError(
                "no DISPLAY for thumbnail capture (pin Xvfb :97 via scripts/gui-isolation.sh)")

        forbidden = set(
            t for t in os.environ.get("MV_FORBIDDEN_DISPLAYS", "").replace(",", " ").split() if t
        )
        if self._display_name in forbidden:
            raise RuntimeError(
                f"display {self._display_name!r} is forbidden (host display; use pinned Xvfb :97)")

        self._bind_functions()
        self._open_display()

    # --- setup helpers ---

    def _bind_functions(self) -> None:
        c = ctypes
        x11, xc, xd, xf = self._x11, self._xcomposite, self._xdamage, self._xfixes

        self._fn_open = _bind_ctypes(x11, "XOpenDisplay", c.c_void_p, [c.c_char_p])
        self._fn_close_dpy = _bind_ctypes(x11, "XCloseDisplay", c.c_int, [c.c_void_p])
        self._fn_sync = _bind_ctypes(x11, "XSync", c.c_int, [c.c_void_p, c.c_int])
        self._fn_flush = _bind_ctypes(x11, "XFlush", c.c_int, [c.c_void_p])
        self._fn_pending = _bind_ctypes(x11, "XPending", c.c_int, [c.c_void_p])
        self._fn_next_event = _bind_ctypes(x11, "XNextEvent", c.c_int, [c.c_void_p, c.c_void_p])
        self._fn_conn_number = _bind_ctypes(x11, "XConnectionNumber", c.c_int, [c.c_void_p])
        self._fn_free = _bind_ctypes(x11, "XFree", c.c_int, [c.c_void_p])
        self._fn_free_pixmap = _bind_ctypes(x11, "XFreePixmap", None, [c.c_void_p, c.c_ulong])
        self._fn_get_geometry = _bind_ctypes(
            x11, "XGetGeometry", c.c_int,
            [c.c_void_p, c.c_ulong, c.POINTER(c.c_ulong), c.POINTER(c.c_int), c.POINTER(c.c_int),
             c.POINTER(c.c_uint), c.POINTER(c.c_uint), c.POINTER(c.c_uint), c.POINTER(c.c_uint)])
        self._fn_get_image = _bind_ctypes(
            x11, "XGetImage", c.c_void_p,
            [c.c_void_p, c.c_ulong, c.c_int, c.c_int, c.c_int, c.c_int, c.c_ulong, c.c_int])
        self._fn_destroy_image = _bind_ctypes(x11, "XDestroyImage", c.c_int, [c.c_void_p])
        self._fn_set_err_handler = _bind_ctypes(
            x11, "XSetErrorHandler", c.c_void_p, [c.c_void_p])

        if xc is not None:
            self._fn_composite_version = _bind_ctypes(
                xc, "XCompositeQueryVersion", c.c_int,
                [c.c_void_p, c.POINTER(c.c_int), c.POINTER(c.c_int)])
            self._fn_redirect = _bind_ctypes(xc, "XCompositeRedirectWindow", None,
                                             [c.c_void_p, c.c_ulong, c.c_int])
            self._fn_unredirect = _bind_ctypes(xc, "XCompositeUnredirectWindow", None,
                                               [c.c_void_p, c.c_ulong, c.c_int])
            self._fn_name_pixmap = _bind_ctypes(xc, "XCompositeNameWindowPixmap", c.c_ulong,
                                                [c.c_void_p, c.c_ulong])
        else:
            self._fn_composite_version = self._fn_redirect = None
            self._fn_unredirect = self._fn_name_pixmap = None

        if xd is not None:
            self._fn_damage_query = _bind_ctypes(
                xd, "XDamageQueryExtension", c.c_int,
                [c.c_void_p, c.POINTER(c.c_int), c.POINTER(c.c_int)])
            self._fn_damage_create = _bind_ctypes(xd, "XDamageCreate", c.c_ulong,
                                                  [c.c_void_p, c.c_ulong, c.c_int])
            self._fn_damage_destroy = _bind_ctypes(xd, "XDamageDestroy", None,
                                                   [c.c_void_p, c.c_ulong])
            self._fn_damage_subtract = _bind_ctypes(xd, "XDamageSubtract", c.c_int,
                                                    [c.c_void_p, c.c_ulong, c.c_ulong, c.c_ulong])
        else:
            self._fn_damage_query = self._fn_damage_create = None
            self._fn_damage_destroy = self._fn_damage_subtract = None

        if xf is not None:
            self._fn_fixes_version = _bind_ctypes(
                xf, "XFixesQueryVersion", c.c_int,
                [c.c_void_p, c.POINTER(c.c_int), c.POINTER(c.c_int)])
            self._fn_fixes_create_region = _bind_ctypes(
                xf, "XFixesCreateRegion", c.c_ulong,
                [c.c_void_p, c.POINTER(_XRectangle), c.c_int])
            self._fn_fixes_destroy_region = _bind_ctypes(xf, "XFixesDestroyRegion", None,
                                                         [c.c_void_p, c.c_ulong])
            self._fn_fixes_fetch_region = _bind_ctypes(
                xf, "XFixesFetchRegion", c.c_void_p,
                [c.c_void_p, c.c_ulong, c.POINTER(c.c_int)])
            self._fn_fixes_subtract_region = _bind_ctypes(
                xf, "XFixesSubtractRegion", None,
                [c.c_void_p, c.c_ulong, c.c_ulong, c.c_ulong])
        else:
            self._fn_fixes_version = self._fn_fixes_create_region = None
            self._fn_fixes_destroy_region = self._fn_fixes_fetch_region = None
            self._fn_fixes_subtract_region = None

    def _open_display(self) -> None:
        c = ctypes
        dpy = self._fn_open(self._display_name.encode("ascii") if self._display_name else None)
        if not dpy:
            raise RuntimeError(f"cannot open display {self._display_name!r} for thumbnail capture")
        self._dpy = dpy
        self._owns_display = True

        # Keep libX11 errors non-fatal during capture: a dead window must
        # degrade to a placeholder, not kill the overview process. The
        # previous handler is restored in close().
        if self._fn_set_err_handler is not None:
            self._err_handler = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_void_p)(
                lambda d, e: 0)
            self._prev_err_handler = self._fn_set_err_handler(self._err_handler)

        try:
            if self._fn_composite_version is not None:
                maj, mnr = c.c_int(0), c.c_int(0)
                if self._fn_composite_version(self._dpy, c.byref(maj), c.byref(mnr)):
                    self._composite_ok = True
        except Exception:
            pass
        try:
            if self._fn_damage_query is not None:
                ev, err = c.c_int(-1), c.c_int(-1)
                if self._fn_damage_query(self._dpy, c.byref(ev), c.byref(err)):
                    self._damage_base = ev.value
        except Exception:
            pass
        try:
            if self._fn_fixes_version is not None:
                maj, mnr = c.c_int(0), c.c_int(0)
                if self._fn_fixes_version(self._dpy, c.byref(maj), c.byref(mnr)):
                    self._fixes_ok = True
        except Exception:
            pass

    # --- properties ---

    @property
    def available(self) -> bool:
        """True when a display is open and the COMPOSITE extension works."""
        return self._dpy is not None and self._composite_ok

    @property
    def live_available(self) -> bool:
        """True when damage-event live updates are possible."""
        return self.available and self._damage_base >= 0

    @property
    def capturing(self) -> bool:
        return self._capturing

    def extensions_info(self) -> Dict[str, Any]:
        return {
            "composite": self._composite_ok,
            "damage": self._damage_base >= 0,
            "fixes": self._fixes_ok,
            "damage_event_base": self._damage_base,
        }

    # --- single-shot capture ---

    def capture_window(self, win_id, max_w: int, max_h: int) -> Dict[str, Any]:
        """Capture a window's content as a scaled RGBA thumbnail.

        Args:
            win_id: window id — int, '0x...' hex string or decimal string
                (accepts enumerate_windows() output directly).
            max_w, max_h: grid cell bounds; the result fits inside them
                with the window's aspect ratio preserved.

        Returns dict:
            win_id (int), width, height, stride (= width*4),
            data (packed RGBA bytes), placeholder (bool),
            error (str, present only on failure paths).
        """
        wid = _parse_window_id(win_id)
        if wid is None:
            return self._placeholder_result(win_id, max_w, max_h, error="invalid window id")
        if not self.available:
            return self._placeholder_result(wid, max_w, max_h, error="XComposite unavailable")

        temp_redirect = wid not in self._redirected
        pixmap = 0
        try:
            if temp_redirect:
                self._fn_redirect(self._dpy, wid, CompositeRedirectAutomatic)
                self._redirected.add(wid)
            self._sync()

            pixmap = self._fn_name_pixmap(self._dpy, wid)
            if not pixmap:
                return self._placeholder_result(
                    wid, max_w, max_h, error="no window pixmap (unmapped or destroyed window?)")

            geo = self._pixmap_geometry(pixmap)
            if not geo or geo["width"] <= 0 or geo["height"] <= 0:
                return self._placeholder_result(wid, max_w, max_h, error="empty pixmap geometry")

            raw = self._pixmap_rgba(pixmap, geo)
            if raw is None:
                return self._placeholder_result(
                    wid, max_w, max_h,
                    error=f"unsupported pixmap format (depth={geo['depth']})")

            tw, th = fit_dimensions(geo["width"], geo["height"], max_w, max_h)
            scaled = _scale_rgba(raw, geo["width"], geo["height"], tw, th)
            return {
                "win_id": wid,
                "width": tw,
                "height": th,
                "stride": tw * 4,
                "data": scaled,
                "placeholder": False,
            }
        except Exception as exc:  # any X step failing degrades, never raises
            return self._placeholder_result(wid, max_w, max_h, error=str(exc))
        finally:
            if pixmap:
                try:
                    self._fn_free_pixmap(self._dpy, pixmap)
                except Exception:
                    pass
            if temp_redirect:
                self._unredirect(wid)

    def _pixmap_geometry(self, pixmap: int) -> Optional[Dict[str, int]]:
        c = ctypes
        root, x, y = c.c_ulong(0), c.c_int(0), c.c_int(0)
        w, h, bw, depth = c.c_uint(0), c.c_uint(0), c.c_uint(0), c.c_uint(0)
        status = self._fn_get_geometry(
            self._dpy, pixmap, c.byref(root), c.byref(x), c.byref(y),
            c.byref(w), c.byref(h), c.byref(bw), c.byref(depth))
        if not status:
            return None
        return {"width": int(w.value), "height": int(h.value), "depth": int(depth.value)}

    def _pixmap_rgba(self, pixmap: int, geo: Dict[str, int]) -> Optional[bytes]:
        c = ctypes
        w, h = geo["width"], geo["height"]
        xi = self._fn_get_image(self._dpy, pixmap, 0, 0, w, h, AllPlanes, ZPixmap)
        if not xi:
            return None
        try:
            img = c.cast(xi, c.POINTER(_XImage)).contents
            if img.byte_order != LSBFirst:
                return None
            if img.bits_per_pixel != 32 or img.width < w or img.height < h:
                return None
            # Named pixmaps report zero masks (no visual attached); window
            # drawables report the TrueColor masks. Either way 32bpp
            # little-endian ZPixmap is B,G,R,X|A on every target we support.
            masks = (img.red_mask, img.green_mask, img.blue_mask)
            if masks not in ((0xFF0000, 0xFF00, 0xFF), (0, 0, 0)):
                return None
            size = img.bytes_per_line * img.height
            buf = c.string_at(img.data, size)
            return _bgra_to_rgba(buf, w, h, img.bytes_per_line, has_alpha=(img.depth == 32))
        finally:
            try:
                self._fn_destroy_image(xi)
            except Exception:
                pass

    def _placeholder_result(self, win_id, max_w: int, max_h: int,
                            error: str = "capture unavailable") -> Dict[str, Any]:
        w = max(1, int(max_w))
        h = max(1, int(max_h))
        wid = _parse_window_id(win_id)
        return {
            "win_id": wid if wid is not None else win_id,
            "width": w,
            "height": h,
            "stride": w * 4,
            "data": _placeholder_rgba(w, h),
            "placeholder": True,
            "error": error,
        }

    # --- live capture lifecycle (damage-driven) ---

    def start_capture(self, win_ids, callback=None) -> bool:
        """Begin damage-tracked live capture for a set of windows.

        Redirects each window (Automatic) and registers an XDamage object
        per window (NonEmpty level) with an XFixes region as the parts
        sink. Call poll_damage() from the caller's event loop; on each
        reported window id, re-run capture_window() to refresh pixels.

        Args:
            win_ids: iterable of window ids (any parseable form).
            callback: optional fn(win_id, area_dict) fired per damage event.

        Returns:
            True when live tracking started, False when damage is
            unavailable (callers then fall back to one-shot capture).
        """
        if self._closed or not self.available:
            return False

        ids = [wid for wid in (_parse_window_id(w) for w in win_ids) if wid is not None]
        for wid in ids:
            if wid not in self._redirected:
                try:
                    self._fn_redirect(self._dpy, wid, CompositeRedirectAutomatic)
                    self._redirected.add(wid)
                except Exception:
                    pass
        if self._damage_base < 0 or self._fn_damage_create is None:
            # Redirection still helps one-shot capture, but no live events.
            return False

        for wid in ids:
            if wid in self._damages:
                continue
            try:
                dmg = self._fn_damage_create(self._dpy, wid, XDamageReportNonEmpty)
                if dmg:
                    self._damages[wid] = dmg
                if self._fixes_ok and self._fn_fixes_create_region is not None:
                    parts = self._fn_fixes_create_region(self._dpy, None, 0)
                    if parts:
                        self._parts[wid] = parts
            except Exception:
                pass
        self._callback = callback
        self._capturing = True
        self._sync()
        return True

    def poll_damage(self, timeout_ms: int = 0) -> List[Dict[str, Any]]:
        """Drain pending XDamage events; non-blocking by default.

        Returns a list of dicts: {'win_id': int, 'area': {x, y, width,
        height}} — the bounding box of accumulated damage (from the XFixes
        parts region when available, else the event's own area). The
        registered callback is invoked as callback(win_id, area) per event.
        """
        if not self._capturing or self._closed:
            return []

        events: List[Dict[str, Any]] = []
        try:
            if timeout_ms > 0 and not self._fn_pending(self._dpy):
                fd = self._fn_conn_number(self._dpy)
                if fd >= 0:
                    select.select([fd], [], [], timeout_ms / 1000.0)
            while self._fn_pending(self._dpy) > 0:
                # sizeof(XEvent) is 192 on libX11 1.8+ (union grew with
                # Xkb/XGE members) and XNextEvent may write the full union:
                # a smaller buffer overflows into the python heap and
                # corrupts it (delayed segfaults). 256 = 192 + margin.
                buf = (ctypes.c_ubyte * 256)()
                self._fn_next_event(self._dpy, buf)
                events.extend(self._handle_event(buf))
        except Exception:
            pass
        return events

    def _handle_event(self, buf) -> List[Dict[str, Any]]:
        c = ctypes
        ev = c.cast(buf, c.POINTER(_XDamageNotifyEvent)).contents
        if ev.type != self._damage_base + XDamageNotify:
            return []  # not ours (Expose etc.) — silently skip

        wid = int(ev.drawable)
        area = {"x": int(ev.area.x), "y": int(ev.area.y),
                "width": int(ev.area.width), "height": int(ev.area.height)}

        dmg = self._damages.get(wid)
        parts = self._parts.get(wid, 0)
        try:
            if dmg:
                self._fn_damage_subtract(self._dpy, dmg, 0, parts)
            if parts and self._fn_fixes_fetch_region is not None:
                fetched = self._fetch_region_bbox(parts)
                if fetched is not None:
                    area = fetched
                # empty the parts region: parts = parts - parts
                self._fn_fixes_subtract_region(self._dpy, parts, parts, parts)
        except Exception:
            pass

        entry = {"win_id": wid, "area": area}
        if self._callback is not None:
            try:
                self._callback(wid, area)
            except Exception:
                pass
        return [entry]

    def _fetch_region_bbox(self, region: int) -> Optional[Dict[str, int]]:
        c = ctypes
        n = c.c_int(0)
        rects = self._fn_fixes_fetch_region(self._dpy, region, c.byref(n))
        if not rects or n.value <= 0:
            if rects:
                try:
                    self._fn_free(rects)
                except Exception:
                    pass
            return None
        try:
            arr = (_XRectangle * n.value).from_address(rects)
            xs = [arr[i].x for i in range(n.value)]
            ys = [arr[i].y for i in range(n.value)]
            x2 = [arr[i].x + arr[i].width for i in range(n.value)]
            y2 = [arr[i].y + arr[i].height for i in range(n.value)]
            x0, y0 = min(xs), min(ys)
            return {"x": x0, "y": y0, "width": max(x2) - x0, "height": max(y2) - y0}
        finally:
            try:
                self._fn_free(rects)
            except Exception:
                pass

    def stop_capture(self) -> None:
        """Stop live tracking and undo every window redirect we own."""
        for wid, dmg in list(self._damages.items()):
            try:
                self._fn_damage_destroy(self._dpy, dmg)
            except Exception:
                pass
        self._damages.clear()
        for wid, parts in list(self._parts.items()):
            try:
                self._fn_fixes_destroy_region(self._dpy, parts)
            except Exception:
                pass
        self._parts.clear()
        for wid in list(self._redirected):
            self._unredirect(wid)
        self._capturing = False
        self._callback = None

    def _unredirect(self, wid: int) -> None:
        if wid in self._redirected:
            try:
                self._fn_unredirect(self._dpy, wid, CompositeRedirectAutomatic)
            except Exception:
                pass
            self._redirected.discard(wid)

    def _sync(self) -> None:
        try:
            self._fn_sync(self._dpy, False)
        except Exception:
            pass

    def close(self) -> None:
        """Full teardown: stop_capture + restore error handler + close display."""
        if self._closed:
            return
        try:
            self.stop_capture()
        except Exception:
            pass
        try:
            if self._fn_set_err_handler is not None and self._prev_err_handler is not None:
                self._fn_set_err_handler(self._prev_err_handler)
        except Exception:
            pass
        if self._owns_display and self._dpy:
            try:
                self._fn_close_dpy(self._dpy)
            except Exception:
                pass
        self._dpy = None
        self._owns_display = False
        self._closed = True

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
