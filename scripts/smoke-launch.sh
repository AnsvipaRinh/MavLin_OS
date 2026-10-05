#!/usr/bin/env bash
# smoke-launch.sh — launch each given mv-* script under Xvfb and require the
# application process itself to stay alive (window constructed) with a
# traceback-free stderr.
#
# Usage: scripts/smoke-launch.sh mv-mail mv-keychain mv-diskutil
#        SMOKE_ALLOW_EXIT=1 scripts/smoke-launch.sh mv-some-oneshot
#
# This catches the class of bug text-based suites cannot see: a broken
# window factory (e.g. passing a class-returning builder where an
# instance-producing factory is required) dies inside Gtk.Application's
# activate handler after import/unit tests already passed.
#
# Reliability notes (lessons from real CI runs):
#  * We track the *interpreter* process (python3/bash running the app), not
#    xvfb-run: Xvfb/xvfb-run startup and teardown latency is of the same
#    order as SMOKE_STAY and used to produce false "stayed up" verdicts for
#    apps that exited immediately (mv-colormeter had no __main__ call at
#    all and still passed locally for weeks).
#  * The whole launch runs in its own session (setsid) and is reaped as a
#    process GROUP: killing only xvfb-run leaked Xvfb/python processes
#    (117 Xvfb left behind on the dev host) until the display pool was
#    exhausted and later apps "failed to start".
#  * Argument-taking helpers get a temp file/dir, so a usage error is not
#    mistaken for a launch failure; one-shot CLI helpers are declared here.
#
# Exit 0 = every requested app stayed up (or exited cleanly when allowed);
# exit 1 = a launch failed.
# Prints a skip line and exits 0 when xvfb-run or the Gtk3 typelib is
# unavailable (e.g. a minimal CI runner without gir1.2-gtk-3.0).
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$REPO/packages/mavericks-apps/src/mavericks-apps/bin"
STAY="${SMOKE_STAY:-4}"
ALLOW_EXIT="${SMOKE_ALLOW_EXIT:-0}"
EXTRA_ALLOW_EXIT="${SMOKE_ONESHOT:-}"
FAILURES=0

if ! command -v xvfb-run >/dev/null 2>&1; then
    echo "ok - smoke skipped (xvfb-run not installed)"
    exit 0
fi

if ! python3 -c "import gi; gi.require_version('Gtk', '3.0')" 2>/dev/null; then
    echo "ok - smoke skipped (Gtk3 typelib not available)"
    exit 0
fi

# Host-display isolation (WSLg leak): capture+forbid the ambient host
# DISPLAY, unset WAYLAND_DISPLAY, and arm the fail-loud guard so any child
# that tries the host display dies with HOST-DISPLAY-BLOCKED instead of
# popping a window on the Windows desktop.  The actual display comes from
# xvfb-run below (already Xvfb-only; never the host).
source "$REPO/scripts/gui-isolation.sh"
mv_gui_isolate

# Apps import the shared runner from /usr/share/mavericks-apps first; when
# that install is absent (CI, fresh checkout) fall back to the repo copy.
# gui-isolation.sh already prepends scripts/gui-guard (sitecustomize.py).
export PYTHONPATH="$REPO/packages/mavericks-apps/src/mavericks-apps/lib${PYTHONPATH:+:$PYTHONPATH}"

# MavLinOS targets X11 (Xfce/xfwm4). The dev host exposes a Wayland
# compositor (WAYLAND_DISPLAY), and without an explicit backend GTK3
# opens the test windows on the *host* compositor instead of the Xvfb
# under test: real host focus/input events then churn (and killed) the
# window under test, and windows popped up on the real desktop. CI has
# no Wayland; forcing x11 makes local runs match CI and the target
# session, and keeps _NET_SUPPORTING_WM_CHECK probing meaningful.
export GDK_BACKEND=x11

SMOKE_TMP="$(mktemp -d)"
printf 'smoke launch file\n' >"$SMOKE_TMP/smoke-file.txt"
cleanup_tmp() { rm -rf "$SMOKE_TMP"; }
trap 'cleanup_tmp; mv_gui_cleanup' EXIT

kill_group() {
    # $1 = leader pid (setsid'ed xvfb-run). Reap the whole session.
    local leader="$1" pgid
    pgid="$(ps -o pgid= -p "$leader" 2>/dev/null | tr -d ' ')"
    if [ -n "$pgid" ]; then
        kill -TERM -- "-$pgid" 2>/dev/null
        sleep 0.3
        kill -KILL -- "-$pgid" 2>/dev/null
    fi
    kill -KILL "$leader" 2>/dev/null
}

find_app_pid() {
    # Full cmdline of the app process: "<interpreter> <path> [args]".
    pgrep -f "^(python3|python|bash|dash|sh) $1" 2>/dev/null | head -n1
}

for app in "$@"; do
    path="$BIN/$app"
    if [[ ! -f "$path" ]]; then
        # installed names use dashes; some repo scripts keep underscores
        # + .py (installed renamed, e.g. mv-launchpad-edit)
        path="$BIN/${app//-/_}.py"
    fi
    if [[ ! -f "$path" ]]; then
        echo "FAIL - smoke $app: script missing ($BIN/$app)"
        FAILURES=$((FAILURES + 1))
        continue
    fi

    # Per-app arguments: helpers that require a target get a temp one, so
    # their real UI opens instead of a usage-exit.
    extra=()
    oneshot=0
    case "$app" in
        mv-getinfo|mv-quicklook|mv-preview|mv-openwith|mv-rename)
            extra=("$SMOKE_TMP/smoke-file.txt")
            ;;
        mv-finder-columns)
            extra=("$SMOKE_TMP")
            ;;
        mv-newfolder)
            # bash one-shot helper (creates a folder, prints, exits rc0)
            extra=("$SMOKE_TMP")
            oneshot=1
            ;;
    esac
    case " $EXTRA_ALLOW_EXIT " in
        *" $app "*) oneshot=1 ;;
    esac

    if [ -x "$path" ]; then
        launch_cmd=("$path")
    else
        launch_cmd=(python3 "$path")
    fi

    log="$(mktemp)"
    setsid xvfb-run -a timeout $((STAY + 4)) "${launch_cmd[@]}" "${extra[@]}" \
        >"$log" 2>&1 &
    job=$!

    # Wait until the app has demonstrably started: either its process is
    # visible, or it already produced output (short-lived one-shots and
    # fast failures can exit before the first poll sees them). Xvfb
    # startup alone is NOT evidence.
    app_pid=""
    started=0
    start_deadline=$((SECONDS + STAY + 3))
    while [ "$SECONDS" -lt "$start_deadline" ]; do
        app_pid="$(find_app_pid "$path")"
        if [ -n "$app_pid" ] || [ -s "$log" ]; then
            started=1
            break
        fi
        sleep 0.1
    done

    if [ "$started" -ne 1 ]; then
        echo "FAIL - smoke $app: app never produced a process or output"
        sed -n '1,20p' "$log" | sed 's/^/      /'
        kill_group "$job"
        wait "$job" 2>/dev/null
        rm -f "$log"
        FAILURES=$((FAILURES + 1))
        continue
    fi

    if [ -n "$app_pid" ]; then
        sleep "$STAY"
    fi
    stayed=0
    if [ -n "$app_pid" ] && kill -0 "$app_pid" 2>/dev/null; then
        stayed=1
    fi
    kill_group "$job"
    wait "$job" 2>/dev/null
    sleep 0.4  # let buffered stderr land in the log before grepping

    if grep -q "HOST-DISPLAY-BLOCKED" "$log"; then
        echo "FAIL - smoke $app: host display attempt blocked by guard"
        grep "HOST-DISPLAY-BLOCKED" "$log" | sed 's/^/      /'
        kill_group "$job"
        wait "$job" 2>/dev/null
        rm -f "$log"
        FAILURES=$((FAILURES + 1))
        continue
    elif grep -q "Traceback" "$log"; then
        echo "FAIL - smoke $app: traceback during launch"
        sed -n '1,20p' "$log" | sed 's/^/      /'
        FAILURES=$((FAILURES + 1))
    elif [ "$stayed" -eq 1 ]; then
        echo "ok - smoke $app: stayed up ${STAY}s"
    elif [ "$oneshot" -eq 1 ] || [ "$ALLOW_EXIT" == "1" ]; then
        echo "ok - smoke $app: exited cleanly within ${STAY}s (oneshot allowed)"
    else
        echo "FAIL - smoke $app: died within ${STAY}s (no traceback)"
        sed -n '1,20p' "$log" | sed 's/^/      /'
        FAILURES=$((FAILURES + 1))
    fi
    rm -f "$log"
done

if [ "$FAILURES" -gt 0 ]; then
    echo "smoke: $FAILURES failure(s)"
    exit 1
fi
echo "ok - smoke launch: $*"
exit 0
