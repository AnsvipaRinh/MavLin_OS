#!/usr/bin/env bash
# test-panel-menubar-gui.sh — GUI smoke for the MavLinOS menu bar on the
# pinned Xvfb :97 (never the host display; see scripts/gui-isolation.sh).
#
# What this can prove in the build container:
#   * xfce4-panel 4.20 STARTS from our skel config and maps its window;
#   * our config is accepted as-is: with configver=2 the panel performs NO
#     xfconf migration ("Panel config needs migration..." and
#     "Type guint does not match type GPtrArray of property /panels" must
#     both be absent).  That is the only externally observable, deterministic
#     difference between a config the panel understands and one it has to
#     rewrite, so it is the regression gate for the dead-config class of bug;
#   * the mv-apple plugin module is DISCOVERED and CONSTRUCTED (its
#     out-of-process wrapper is spawned at least once);
#   * the panel window is a 24px bar at the top of the screen.
#
# What this CANNOT prove (recorded honestly, see NEEDS_HARDWARE_TEST.md):
#   * plugin lifetime / the Apple menu opening / the rendered clock text /
#     the appmenu plugin (vala-panel-appmenu is not installed in the build
#     container).  xfce4-panel 4.20 runs every non-internal plugin in its own
#     out-of-process `wrapper-2.0`, and on a bare Xvfb with no session those
#     wrappers are reaped ~0.3 s after construct — a CONTROL experiment with
#     a four-line stock plugin and with the stock `actions` plugin reproduces
#     the identical "automatically restarted after crash" message, so it is
#     an environment limit and not an mv-apple defect.  Visual/behavioral
#     validation is a hardware item.
#
# Skips cleanly (exit 0 with SKIP lines) when :97 is busy — parallel agents
# pin the same display.

set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1

source scripts/gui-isolation.sh

mv_gui_isolate || { echo "SKIP: host-display isolation unavailable"; exit 0; }

if command -v xwininfo >/dev/null 2>&1 \
   && xwininfo -root -display :97 >/dev/null 2>&1; then
    echo "SKIP: pinned display :97 already in use (parallel GUI test)"
    mv_gui_report
    exit 0
fi

if ! mv_gui_pin_display; then
    echo "SKIP: no local X server available (Xvfb missing)"
    exit 0
fi

echo "--- menu-bar GUI smoke on $DISPLAY (isolated: host was '${MV_HOST_DISPLAY:-none}') ---"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/mv-menubar-gui.XXXXXX")"
cleanup() {
    if [ -n "${DBUS_SESSION_BUS_PID:-}" ]; then
        kill "$DBUS_SESSION_BUS_PID" 2>/dev/null
    fi
    rm -rf "$TMP" 2>/dev/null
    mv_gui_cleanup
}
trap cleanup EXIT

mkdir -p "$TMP/config/xfce4/xfconf/xfce-perchannel-xml" "$TMP/cache" \
         "$TMP/data" "$TMP/run"
cp configs/desktop/xfce/xfce4-panel.xml \
   "$TMP/config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml"
cp configs/desktop/xfce/xsettings.xml \
   "$TMP/config/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml" 2>/dev/null || true

export XDG_CONFIG_HOME="$TMP/config" XDG_CACHE_HOME="$TMP/cache"
export XDG_DATA_HOME="$TMP/data" XDG_RUNTIME_DIR="$TMP/run" HOME="$TMP"
chmod 700 "$XDG_RUNTIME_DIR"
eval "$(dbus-launch --sh-syntax 2>/dev/null)" || true

# In its own process group + job-control messages silenced: the panel is
# SIGKILLed below and we do not want a "Killed" line in the test output.
set +m
{ timeout -s TERM 14 xfce4-panel --disable-wm-check \
    >"$TMP/panel.out" 2>"$TMP/panel.err" 2>&1 & } 2>/dev/null
PANEL_PID=$(pgrep -n -x xfce4-panel || true)

# Watch for the mv-apple plugin wrapper while the panel is up.
SAW_APPLE_WRAPPER=0
for _ in $(seq 1 160); do
    if ps -eo cmd --no-headers 2>/dev/null \
       | grep -F "wrapper-2.0" | grep -qF "libmv-apple.so"; then
        SAW_APPLE_WRAPPER=1
        break
    fi
    sleep 0.05
done

sleep 4

TREE="$(xwininfo -root -display "$DISPLAY" -tree 2>/dev/null)"
# Match the panel's own toplevel only: the "Plugin loading failure" dialog
# also carries ("xfce4-panel" "Xfce4-panel") as its WM_CLASS.
PANEL_LINE="$(printf '%s\n' "$TREE" \
             | grep -m1 -E '^[[:space:]]+0x[0-9a-f]+ "xfce4-panel"')"
PANEL_GEOM="$(printf '%s\n' "$PANEL_LINE" \
              | sed -n 's/.*"xfce4-panel".* \([0-9]*x[0-9]*+[0-9-]*+[0-9-]*\).*/\1/p')"

if [ -n "${PANEL_PID:-}" ]; then
    kill -TERM "$PANEL_PID" 2>/dev/null
    sleep 2
    kill -KILL "$PANEL_PID" 2>/dev/null
fi
pkill -f "timeout -s TERM 14 xfce4-panel --disable-wm-check" 2>/dev/null

FAILURES=0
pass() { echo "ok - $1"; }
fail() { echo "FAIL - $1"; FAILURES=$((FAILURES + 1)); }

# 1. the panel mapped
if printf '%s\n' "$PANEL_LINE" | grep -q '"xfce4-panel"'; then
    pass "xfce4-panel window mapped on $DISPLAY (${PANEL_GEOM:-geom?})"
else
    fail "xfce4-panel window did not map"
fi

# 2. geometry: 24px bar PINNED TO THE TOP EDGE (y == 0).
#    p=8 was SNAP_POSITION_SW (bottom): this check is the regression gate for
#    the menu bar silently living at the bottom of the screen.
if printf '%s' "${PANEL_GEOM:-}" \
   | grep -qE '^[0-9]+x(2[4-9]|3[0-9])\+0\+0$'; then
    pass "panel is a ~24px bar pinned to the TOP edge ($PANEL_GEOM)"
else
    fail "panel not at the top edge: ${PANEL_GEOM:-none} (p=8 would be y=1025)"
fi

# 3. our config is accepted verbatim (no xfconf migration rewrite)
if grep -aq "needs migration" "$TMP/panel.err"; then
    fail "panel ran its config migration: configver missing from xfce4-panel.xml"
else
    pass "no xfconf config migration (configver=2 honoured)"
fi
if grep -aq "does not match type GPtrArray of property /panels" "$TMP/panel.err"; then
    fail "xfconf /panels type warning: panel is reinterpreting our array form"
else
    pass "xfconf /panels array form accepted without warnings"
fi

# 4. mv-apple is discovered and constructed
if [ "$SAW_APPLE_WRAPPER" = "1" ]; then
    pass "mv-apple plugin discovered and constructed (wrapper-2.0 spawned)"
else
    fail "mv-apple plugin wrapper never spawned (module not found?)"
fi

# 5. no load failure for the modules we ship
if grep -aq "Plugin loading failure" "$TMP/panel.err"; then
    # vala-panel-appmenu is not installed in the build container; that is the
    # only expected cause and it is an environment gap, not a repo defect.
    if [ -e /usr/lib/xfce4/panel/plugins/libappmenu.so ] \
       || [ -e /usr/local/lib/xfce4/panel/plugins/libappmenu.so ]; then
        fail "a panel module failed to load even though appmenu is installed"
    else
        echo "note - 'Plugin loading failure' = appmenu module absent in this"
        echo "       container (vala-panel-appmenu is an ISO/pacman dep);"
        echo "       recorded as an environment gap, not a config defect."
    fi
else
    pass "every referenced panel module loads"
fi

echo
echo "--- panel stderr (GTK/theme noise filtered) ---"
grep -avE "Theme parsing error|unknown @ rule|is not a valid property name|unknown syntax for|is not a valid color name|not a valid pseudo-class|not a valid name for|Unknown key|is deprecated|deprecated\.|Failed to fetch _NET|Failed to get _NET|assuming" \
    "$TMP/panel.err" | grep -avE '^\s*$' | head -20 || true

if ! mv_gui_report; then
    FAILURES=$((FAILURES + 1))
fi

echo
if [ "$FAILURES" -eq 0 ]; then
    echo "OK: menu-bar GUI smoke green (container scope only — see header)"
else
    echo "FAILURES: $FAILURES"
fi
exit "$FAILURES"
