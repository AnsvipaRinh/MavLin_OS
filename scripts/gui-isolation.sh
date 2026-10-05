#!/usr/bin/env bash
# gui-isolation.sh — keep GUI tests OFF the host display (WSLg → Windows leak).
#
# Sourced, not executed:
#   source scripts/gui-isolation.sh
#   mv_gui_isolate        # env + fail-loud guard (idempotent)
#   mv_gui_pin_display    # dedicated Xvfb, exports DISPLAY (idempotent)
#   mv_gui_report         # print isolation status + guard violations (gates use it)
#
# Why: the dev host is WSLg — DISPLAY=:0 and WAYLAND_DISPLAY=wayland-0 both
# forward to the user's Windows desktop.  Every test-mv-*.py GUI smoke uses
# HAS_DISPLAY = bool(WAYLAND_DISPLAY or DISPLAY), which is TRUE there, so a
# plain test run popped real windows on the host desktop.  Isolation does:
#   * capture the ambient host DISPLAY/WAYLAND_DISPLAY as FORBIDDEN
#   * unset WAYLAND_DISPLAY (WSLg wayland socket never reached)
#   * force GDK_BACKEND=x11 (MavLinOS targets X11/Xfce anyway)
#   * point DISPLAY at a dedicated Xvfb (its own display number, never the
#     host :0) so mapped windows land on an
#     invisible local server instead of the Windows desktop
#   * prepend scripts/gui-guard to PYTHONPATH: sitecustomize.py aborts any
#     Python process (exit 125, HOST-DISPLAY-BLOCKED) that re-introduces the
#     host display or a wayland backend — fail loud, never pop a window
#
# Violations append to $MV_GUARD_LOG; mv_gui_report prints them as gate FAIL.

MV_GUI_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MV_GUI_GUARD_DIR="$MV_GUI_ROOT/scripts/gui-guard"

mv_gui_ensure_guard_path() {
    case ":${PYTHONPATH:-}:" in
        *":$MV_GUI_GUARD_DIR:"*) ;;
        *) PYTHONPATH="$MV_GUI_GUARD_DIR${PYTHONPATH:+:$PYTHONPATH}" ;;
    esac
    export PYTHONPATH
}

mv_gui_isolate() {
    if [ "${MV_GUI_ISOLATED:-0}" = "1" ]; then
        mv_gui_ensure_guard_path
        return 0
    fi
    MV_HOST_DISPLAY="${DISPLAY:-}"
    MV_HOST_WAYLAND="${WAYLAND_DISPLAY:-}"
    unset WAYLAND_DISPLAY
    export GDK_BACKEND=x11
    export MV_GUI_ISOLATED=1
    export MV_FORBIDDEN_DISPLAYS="$MV_HOST_DISPLAY"
    MV_GUARD_LOG="$(mktemp "${TMPDIR:-/tmp}/mv-gui-guard.XXXXXX")" || return 1
    export MV_GUARD_LOG
    mv_gui_ensure_guard_path
    trap 'mv_gui_cleanup' EXIT
    return 0
}

mv_gui_display_ok() {
    # Real client connection probe (libX11) — the only reliable readiness
    # test here: WSLg mounts /tmp/.X11-unix read-only, so Xvfb falls back
    # to an abstract socket and a filesystem -S test can never succeed.
    local d="$1"
    if command -v xwininfo >/dev/null 2>&1; then
        xwininfo -root -display "$d" >/dev/null 2>&1
    elif command -v xdpyinfo >/dev/null 2>&1; then
        xdpyinfo -display "$d" >/dev/null 2>&1
    else
        return 1
    fi
}

mv_gui_pin_display() {
    # Reuse this shell's Xvfb if we already started one.
    if [ "${MV_XVFB_OWNED:-0}" = "1" ] && [ -n "${MV_XVFB_PID:-}" ] \
            && kill -0 "$MV_XVFB_PID" 2>/dev/null; then
        export DISPLAY="$MV_XVFB_DISPLAY"
        return 0
    fi
    if ! command -v Xvfb >/dev/null 2>&1; then
        # No local X server available: behave headless (suites skip GUI)
        # rather than falling back to the host display.
        unset DISPLAY
        return 1
    fi
    # Dedicated display, explicit number (NOT -displayfd: its listener
    # creation is unreliable on the WSLg read-only /tmp/.X11-unix).
    # Never :0 — that is the WSLg host server forwarding to Windows.
    MV_XVFB_DISPLAY=":97"
    if mv_gui_display_ok "$MV_XVFB_DISPLAY"; then
        # A live local Xvfb already answers on :97 (concurrent run): reuse.
        MV_XVFB_OWNED=0
        export DISPLAY="$MV_XVFB_DISPLAY"
        return 0
    fi
    Xvfb "$MV_XVFB_DISPLAY" -screen 0 1680x1050x24 -nolisten tcp \
        >/dev/null 2>&1 &
    MV_XVFB_PID=$!
    MV_XVFB_OWNED=1
    local i=0
    while [ "$i" -lt 50 ]; do
        mv_gui_display_ok "$MV_XVFB_DISPLAY" && break
        kill -0 "$MV_XVFB_PID" 2>/dev/null || break
        sleep 0.1
        i=$((i + 1))
    done
    if mv_gui_display_ok "$MV_XVFB_DISPLAY"; then
        export DISPLAY="$MV_XVFB_DISPLAY"
        export MV_XVFB_DISPLAY
        return 0
    fi
    kill "$MV_XVFB_PID" 2>/dev/null
    wait "$MV_XVFB_PID" 2>/dev/null
    MV_XVFB_OWNED=0
    unset DISPLAY
    return 1
}

mv_gui_report() {
    echo "--- host-display guard (GUI tests must never touch the host) ---"
    if [ -n "${MV_GUARD_LOG:-}" ] && [ -s "$MV_GUARD_LOG" ]; then
        echo "FAIL: host-display guard: $(wc -l <"$MV_GUARD_LOG") blocked attempt(s)"
        sed 's/^/    | /' "$MV_GUARD_LOG"
        return 1
    fi
    echo "OK: host-display guard: 0 attempts (DISPLAY=${DISPLAY:-unset}, WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-unset}, GDK_BACKEND=${GDK_BACKEND:-unset})"
    return 0
}

mv_gui_cleanup() {
    if [ "${MV_XVFB_OWNED:-0}" = "1" ] && [ -n "${MV_XVFB_PID:-}" ]; then
        kill "$MV_XVFB_PID" 2>/dev/null
        wait "$MV_XVFB_PID" 2>/dev/null
        local num="${MV_XVFB_DISPLAY:-}"
        num="${num#*:}"
        [ -n "$num" ] && rm -f "/tmp/.X${num}-lock" 2>/dev/null
        MV_XVFB_OWNED=0
    fi
    if [ -n "${MV_GUARD_LOG:-}" ] && [ ! -s "$MV_GUARD_LOG" ]; then
        rm -f "$MV_GUARD_LOG" 2>/dev/null
    fi
    return 0
}
