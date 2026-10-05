#!/usr/bin/env python3
"""Mission Control — damage-driven live thumbnail updates (O6).

While the overview window is open, window content changes are picked up
EVENT-DRIVEN: XDamage reports arrive on the ThumbnailCapture connection,
a GLib io-watch on that connection's file descriptor wakes the
controller, which drains the damage events and recaptures only the
windows that actually changed. No polling loop, no idle timers — the
only "active" thing between damage events is the fd watch the main loop
already multiplexes (§7).

Lifecycle contract:
- start(win_ids, sizes): redirect + damage-track the given windows,
  install the fd watch. Returns False when damage is unavailable —
  the caller keeps its static one-shot captures (placeholder fallback).
- stop(): remove the watch, stop_capture(), close() — after stop() the
  process holds no redirects, no damage objects, no open display from
  this module. Zero residual state.
"""
from typing import Callable, Dict, Optional, Tuple

from mission_control_thumbnail import ThumbnailCapture


class LiveThumbnails:
    """Feed live window pixels into an open Mission Control overview."""

    def __init__(self, capture: ThumbnailCapture,
                 on_window_updated: Callable[[int, object], None],
                 watch_add: Optional[Callable] = None,
                 watch_remove: Optional[Callable] = None):
        """`on_window_updated(win_id, pixbuf)` fires per damaged window.

        watch_add/watch_remove are injectable for headless tests; the
        default binds GLib.io_add_watch / GLib.source_remove.
        """
        self._capture = capture
        self._on_window_updated = on_window_updated
        self._sizes: Dict[int, Tuple[int, int]] = {}
        self._watch_id = None
        self._watch_remove = watch_remove
        self._started = False
        if watch_add is not None:
            self._watch_add = watch_add
        else:
            import gi
            gi.require_version("GLib", "2.0")
            from gi.repository import GLib
            self._watch_add = lambda fd, cb: GLib.io_add_watch(
                fd, GLib.PRIORITY_DEFAULT, GLib.IO_IN, cb)

    @property
    def started(self) -> bool:
        return self._started

    def start(self, window_sizes: Dict[int, Tuple[int, int]]) -> bool:
        """Begin live tracking for {win_id: (max_w, max_h)} windows.

        Returns True when damage events will flow; False means the
        caller must keep its static captures.
        """
        if self._started:
            return True
        if not self._capture.live_available:
            return False
        self._sizes = dict(window_sizes)
        win_ids = [wid for wid in self._sizes if wid is not None]
        if not self._capture.start_capture(win_ids):
            return False

        fd = self.connection_fd
        if fd is None or fd < 0:
            self._capture.stop_capture()
            return False
        self._watch_id = self._watch_add(fd, self._on_readable)
        self._started = True
        return True

    @property
    def connection_fd(self) -> Optional[int]:
        fd = getattr(self._capture, "connection_fd", None)
        if isinstance(fd, int):
            return fd if fd >= 0 else None
        if callable(fd):
            try:
                value = int(fd())
                return value if value >= 0 else None
            except Exception:
                return None
        fn = getattr(self._capture, "_fn_conn_number", None)
        dpy = getattr(self._capture, "_dpy", None)
        if fn is not None and dpy is not None:
            try:
                return int(fn(dpy))
            except Exception:
                return None
        return None

    def _on_readable(self, *_args) -> bool:
        """GLib io-watch callback: drain damage, recapture changed windows.

        Returns True to keep the watch installed; stop() removes it.
        """
        if not self._started:
            return False
        try:
            events = self._capture.poll_damage(timeout_ms=0)
        except Exception:
            return True
        for event in events:
            wid = event.get("win_id")
            size = self._sizes.get(wid)
            if size is None:
                continue
            self.refresh(wid, size)
        return True

    def refresh(self, win_id: int, size: Tuple[int, int]) -> None:
        """Recapture one window now and hand the pixbuf to the callback."""
        from mission_control_previews import rgba_to_pixbuf
        try:
            result = self._capture.capture_window(win_id, size[0], size[1])
            if result.get("placeholder"):
                return
            pixbuf = rgba_to_pixbuf(result)
        except Exception:
            return
        try:
            self._on_window_updated(win_id, pixbuf)
        except Exception:
            pass

    def stop(self) -> None:
        """Tear everything down: watch, damage tracking, redirects, display."""
        if self._watch_id is not None:
            if self._watch_remove is not None:
                try:
                    self._watch_remove(self._watch_id)
                except Exception:
                    pass
            else:
                try:
                    import gi
                    gi.require_version("GLib", "2.0")
                    from gi.repository import GLib
                    GLib.source_remove(self._watch_id)
                except Exception:
                    pass
            self._watch_id = None
        self._started = False
        self._sizes = {}
        try:
            self._capture.stop_capture()
        except Exception:
            pass
        try:
            self._capture.close()
        except Exception:
            pass
