#!/usr/bin/env python3
"""Mission Control XComposite thumbnail capture.

One-shot, read-only capture of a mapped X11 window. Uses
XCompositeNameWindowPixmap (no manual redirection) and XGetImage, then
converts the pixels to a GdkPixbuf RGB image.
"""
import ctypes
import ctypes.util
from typing import Optional, Tuple

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
    if bits <= 0:
        return 0
    maximum = (1 << bits) - 1
    return 255 if maximum == 255 else (value * 255 + maximum // 2) // maximum

def _image_to_rgb(image: _XImage) -> bytearray:
    """Convert an XImage to packed RGB888."""
    if image.bits_per_pixel not in (16, 24, 32):
        raise RuntimeError(f"unsupported bits_per_pixel={image.bits_per_pixel}")
    width, height = image.width, image.height
    bpp = (image.bits_per_pixel + 7) // 8
    raw = ctypes.string_at(image.data, image.bytes_per_line * height)
    rshift, rbits = _mask_shift(int(image.red_mask))
    gshift, gbits = _mask_shift(int(image.green_mask))
    bshift, bbits = _mask_shift(int(image.blue_mask))
    endian = "little" if image.byte_order == 0 else "big"
    out = bytearray(width * height * 3)
    pos = 0
    for y in range(height):
        row = y * image.bytes_per_line
        for x in range(width):
            start = row + x * bpp
            pixel = int.from_bytes(raw[start:start + bpp], endian)
            out[pos:pos + 3] = bytes((
                _scale_channel((pixel & int(image.red_mask)) >> rshift, rbits),
                _scale_channel((pixel & int(image.green_mask)) >> gshift, gbits),
                _scale_channel((pixel & int(image.blue_mask)) >> bshift, bbits),
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
