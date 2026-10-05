#!/usr/bin/env python3
"""Mission Control — per-workspace composite thumbnails for the Spaces strip.

A Mavericks Space thumbnail is a miniature of the whole desktop: the
desktop background with that Space's windows at their scaled positions.
X11 has no direct "capture another workspace" primitive, so a preview is
composed from one-shot window captures (mission_control_thumbnail
backends) placed at scaled window geometries over a scaled wallpaper.

§7 compliance: everything here runs only while the overview is open —
a handful of one-shot captures per workspace, no daemon, no polling, no
redirects. When the overview closes nothing from this module survives.

Layout math (place_windows) is pure and unit-testable without X11/GTK;
rendering (compose_preview) needs only GdkPixbuf, never a display.
"""
import os
from typing import Any, Dict, List, Optional, Tuple

Preview = Dict[str, Any]

# How many windows a single workspace preview composes (largest first by
# area, most relevant kept by the caller's ordering). Bounds the one-shot
# capture cost of a busy desktop while keeping the miniature informative.
MAX_WINDOWS_PER_PREVIEW = 8

# Mavericks desktop background fallback (deep blue-grey, era-correct).
FALLBACK_BACKGROUND = 0x2C3E50FF

WALLPAPER_CANDIDATES = (
    "/usr/share/backgrounds/mavericks/mavericks-desktop.png",
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "..", "..",
        "mavericks-theme", "src", "mavericks-theme", "wallpapers",
        "mavericks-desktop.png",
    ),
)


def rgba_to_pixbuf(result: Dict[str, Any]):
    """Convert a ThumbnailCapture result dict to an RGB GdkPixbuf.

    ThumbnailCapture.capture_window returns packed RGBA bytes; GTK
    previews are RGB — alpha is stripped per channel (vectorized).
    """
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf

    width, height = int(result["width"]), int(result["height"])
    src = result["data"]
    rgb = bytearray(width * height * 3)
    rgb[0::3] = src[0::4]
    rgb[1::3] = src[1::4]
    rgb[2::3] = src[2::4]
    return GdkPixbuf.Pixbuf.new_from_data(
        bytes(rgb), GdkPixbuf.Colorspace.RGB, False, 8,
        width, height, width * 3, None, None)


def place_windows(
    windows: List[Dict[str, Any]],
    screen_w: int,
    screen_h: int,
    thumb_w: int,
    thumb_h: int,
    pad: int = 2,
) -> List[Preview]:
    """Map window geometries into workspace-thumbnail coordinates.

    Pure function. Each window's absolute (x, y, width, height) is scaled
    by thumb/screen and clamped into the thumbnail; windows larger than
    the screen (or with broken geometry) fall back to a centered tile.
    Order is preserved (caller controls z-order/relevance priority).
    """
    if screen_w <= 0 or screen_h <= 0 or thumb_w <= 0 or thumb_h <= 0:
        return []
    scale = min(thumb_w / screen_w, thumb_h / screen_h)
    ox = (thumb_w - screen_w * scale) / 2.0
    oy = (thumb_h - screen_h * scale) / 2.0

    placed = []
    for win in windows:
        geo = win.get("geometry") or {}
        try:
            gx, gy = int(geo.get("x", 0)), int(geo.get("y", 0))
            gw, gh = int(geo.get("width", 0)), int(geo.get("height", 0))
        except (TypeError, ValueError):
            continue
        if gw <= 0 or gh <= 0:
            continue
        if gw > screen_w or gh > screen_h:
            # Geometry outside the screen model: center it as a tile.
            gw = min(gw, screen_w)
            gh = min(gh, screen_h)
            gx = (screen_w - gw) // 2
            gy = (screen_h - gh) // 2
        x = ox + gx * scale
        y = oy + gy * scale
        w = max(1.0, gw * scale)
        h = max(1.0, gh * scale)
        x = max(0.0, min(x, thumb_w - w))
        y = max(0.0, min(y, thumb_h - h))
        placed.append({
            "win_id": win.get("win_id"),
            "x": int(round(x)),
            "y": int(round(y)),
            "w": int(round(w)),
            "h": int(round(h)),
        })
    # Clip every rect into the thumbnail (pad inset), keep order.
    result = []
    for p in placed:
        x0 = max(pad, min(p["x"], thumb_w - 1 - pad))
        y0 = max(pad, min(p["y"], thumb_h - 1 - pad))
        x1 = min(p["x"] + p["w"], thumb_w - pad)
        y1 = min(p["y"] + p["h"], thumb_h - pad)
        if x1 - x0 >= 1 and y1 - y0 >= 1:
            result.append({"win_id": p["win_id"], "x": x0, "y": y0,
                           "w": x1 - x0, "h": y1 - y0})
    return result


def load_background(thumb_w: int, thumb_h: int,
                    wallpaper_path: Optional[str] = None):
    """Return a thumb-sized GdkPixbuf background, or None if unavailable.

    Uses GdkPixbuf only — no display connection. Resolution order:
    explicit path, $MV_MC_WALLPAPER, the installed Mavericks wallpaper,
    the repo-local development copy. Invalid files degrade to None
    (caller fills the solid fallback color).
    """
    try:
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf
    except (ImportError, ValueError):
        return None

    candidates: List[str] = []
    if wallpaper_path:
        candidates.append(wallpaper_path)
    env_path = os.environ.get("MV_MC_WALLPAPER")
    if env_path:
        candidates.append(env_path)
    candidates.extend(WALLPAPER_CANDIDATES)

    for path in candidates:
        try:
            if not os.path.isfile(path):
                continue
            pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                path, thumb_w, thumb_h, False)
            return pb
        except Exception:
            continue
    return None


def compose_preview(
    placed: List[Preview],
    thumb_w: int,
    thumb_h: int,
    capture_fn=None,
    background=None,
) -> Any:
    """Render placed window rects over a background into a GdkPixbuf.

    capture_fn(win_id, (w, h)) -> GdkPixbuf or None (same contract as
    mission_control_thumbnail.capture_window). Uncapturable windows get a
    flat placeholder tile — the placeholder-fallback contract survives.
    `background` may be a pre-scaled GdkPixbuf or None (solid fill).
    """
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf

    if background is not None:
        preview = background.copy()
    else:
        preview = GdkPixbuf.Pixbuf.new(
            GdkPixbuf.Colorspace.RGB, False, 8, thumb_w, thumb_h)
        preview.fill(FALLBACK_BACKGROUND)

    for item in placed:
        w, h = item["w"], item["h"]
        cap = None
        if capture_fn is not None:
            try:
                cap = capture_fn(item["win_id"], (w, h))
            except Exception:
                cap = None
        if cap is None:
            # Placeholder tile: neutral grey, unmistakably "no pixels".
            tile = GdkPixbuf.Pixbuf.new(
                GdkPixbuf.Colorspace.RGB, False, 8, w, h)
            tile.fill(0x9A9A9AFF)
            cap = tile
        elif cap.get_width() > w or cap.get_height() > h:
            cap = cap.scale_simple(
                min(w, cap.get_width()), min(h, cap.get_height()),
                GdkPixbuf.InterpType.BILINEAR)
        # Center the (aspect-preserved) capture inside its placed rect.
        dx = item["x"] + max(0, (w - cap.get_width()) // 2)
        dy = item["y"] + max(0, (h - cap.get_height()) // 2)
        dw = min(cap.get_width(), thumb_w - dx)
        dh = min(cap.get_height(), thumb_h - dy)
        if dw > 0 and dh > 0:
            cap.copy_area(0, 0, dw, dh, preview, dx, dy)
    return preview


def build_workspace_previews(
    by_desktop: Dict[int, List[Dict[str, Any]]],
    screen_w: int,
    screen_h: int,
    thumb_size: Tuple[int, int],
    capture_fn=None,
    wallpaper_path: Optional[str] = None,
    desktop_count: Optional[int] = None,
) -> Dict[int, Any]:
    """One-shot preview per workspace: {desktop index: GdkPixbuf}.

    `by_desktop` maps desktop index -> window dicts (enumerate_windows()
    shape); desktops without windows still get a background-only preview
    (the 'empty workspace placeholder'). Windows beyond
    MAX_WINDOWS_PER_PREVIEW are dropped, largest-area first is the
    caller's ordering choice — this function keeps the given order.
    """
    thumb_w, thumb_h = thumb_size
    background = load_background(thumb_w, thumb_h, wallpaper_path)
    previews: Dict[int, Any] = {}
    desktops = sorted(by_desktop.keys())
    if desktop_count is not None:
        desktops = list(range(max(1, int(desktop_count))))
        for desk in by_desktop:
            if desk not in desktops:
                desktops.append(desk)
    for desk in desktops:
        windows = list(by_desktop.get(desk, []))[:MAX_WINDOWS_PER_PREVIEW]
        placed = place_windows(windows, screen_w, screen_h, thumb_w, thumb_h)
        previews[desk] = compose_preview(
            placed, thumb_w, thumb_h, capture_fn=capture_fn,
            background=background.copy() if background is not None else None)
    return previews
