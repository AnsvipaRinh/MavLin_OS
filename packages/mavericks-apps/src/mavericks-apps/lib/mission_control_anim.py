#!/usr/bin/env python3
"""Mission Control — animation timeline model (O6 choreography).

Pure time-math, no GTK/GLib/X11: a Timeline maps elapsed milliseconds to
an eased 0..1 progress value; an Animator is a tick-source-agnostic
registry that dispatches progress to callbacks and self-removes finished
timelines. The GTK layer (mv-mc-overview) drives it from a short-lived
16ms ticker that exists ONLY while at least one timeline is alive — no
permanent timers (§7: nothing animates while the overview sits idle).

Mavericks choreography parameters:
- ENTRANCE_MS 160 / EXIT_MS 140 — inside the plan's 150ms ± 20ms window;
- ease-out cubic: fast settle, no bounce (Mavericks has no spring);
- per-card directional offset: each thumbnail starts displaced toward
  its window's real on-screen position (12% of the delta, capped) and
  settles into its grid slot — the perceptual "fly from the window"
  without a full-geometry traversal.

Reduced motion: when_mv_reduced_motion() gates every choreography; the
caller skips timelines entirely (instant show/destroy).
"""
import os
import subprocess
from typing import Callable, List, Optional, Tuple

ENTRANCE_MS = 160
EXIT_MS = 140
# Fraction of the window->grid delta used as the card's start offset.
DIRECTIONAL_PULL = 0.12
# Cap so far-away windows don't slide absurd distances (pixels).
DIRECTIONAL_MAX_PX = 48


def ease_out_cubic(t: float) -> float:
    """Mavericks-style settle curve: fast start, smooth landing."""
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    inv = 1.0 - t
    return 1.0 - inv * inv * inv


class Timeline:
    """Eased 0..1 progress over `duration_ms`, driven by absolute time."""

    def __init__(self, duration_ms: int, ease: Callable[[float], float] = ease_out_cubic,
                 start_at_ms: float = 0.0):
        self.duration_ms = max(0.0, float(duration_ms))
        self.ease = ease
        self.start_at_ms = float(start_at_ms)

    def raw(self, now_ms: float) -> float:
        """Un-eased linear progress, clamped to [0, 1]."""
        if self.duration_ms <= 0.0:
            return 1.0
        elapsed = float(now_ms) - self.start_at_ms
        if elapsed <= 0.0:
            return 0.0
        return min(1.0, elapsed / self.duration_ms)

    def value(self, now_ms: float) -> float:
        """Eased progress in [0, 1]."""
        return self.ease(self.raw(now_ms))

    def done(self, now_ms: float) -> bool:
        return self.raw(now_ms) >= 1.0


class Animator:
    """Registry of (timeline, callback) pairs dispatched by tick(now_ms).

    The caller owns the clock (GLib ticker, mocked time in tests). Each
    tick fires callback(progress) for every live timeline, drops finished
    ones and reports whether anything is still animating — the GTK layer
    stops its ticker as soon as this returns False.
    """

    def __init__(self):
        self._items: List[Tuple[Timeline, Callable[[float], None]]] = []

    def add(self, timeline: Timeline, callback: Callable[[float], None]) -> Timeline:
        self._items.append((timeline, callback))
        return timeline

    @property
    def active(self) -> bool:
        return bool(self._items)

    def tick(self, now_ms: float) -> bool:
        """Dispatch one frame; returns True while animations remain."""
        still: List[Tuple[Timeline, Callable[[float], None]]] = []
        for timeline, callback in self._items:
            if not timeline.done(now_ms):
                try:
                    callback(timeline.value(now_ms))
                except Exception:
                    pass
                still.append((timeline, callback))
            else:
                try:
                    callback(1.0)
                except Exception:
                    pass
        self._items = still
        return bool(still)


def directional_offset(win_x: float, win_y: float,
                       grid_x: float, grid_y: float) -> Tuple[float, float]:
    """Start offset pulling a card toward its window's screen position.

    Pure function: 12% of the window->grid delta, capped at
    DIRECTIONAL_MAX_PX per axis. The card slides from this offset to
    (0, 0) as the entrance timeline progresses — i.e. it visually leaves
    the window's position and settles into its grid slot.
    """
    dx = (win_x - grid_x) * DIRECTIONAL_PULL
    dy = (win_y - grid_y) * DIRECTIONAL_PULL
    def cap(v: float) -> float:
        return max(-DIRECTIONAL_MAX_PX, min(DIRECTIONAL_MAX_PX, v))
    return (cap(dx), cap(dy))


def lerp_offset(offset_x: float, offset_y: float, progress: float) -> Tuple[float, float]:
    """Offset at `progress`: full offset at 0, (0, 0) at 1."""
    return (offset_x * (1.0 - progress), offset_y * (1.0 - progress))


def when_mv_reduced_motion(env=None) -> bool:
    """True when animation must be skipped.

    Order: $MV_REDUCED_MOTION (1/true/yes) wins; then the Xfce xsettings
    animation toggle (read via xfconf-query when available); absence of
    both means full motion. Never raises, never blocks long.
    """
    env = env if env is not None else os.environ
    flag = (env.get("MV_REDUCED_MOTION") or "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    if flag in ("0", "false", "no", "off"):
        return False
    try:
        out = subprocess.run(
            ["xfconf-query", "-c", "xsettings", "-p", "/Gtk/EnableAnimations"],
            capture_output=True, text=True, timeout=1,
        )
        if out.returncode == 0 and out.stdout.strip().lower() == "false":
            return True
    except Exception:
        pass
    return False
