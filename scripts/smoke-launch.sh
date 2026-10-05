#!/usr/bin/env bash
# smoke-launch.sh — launch each given mv-* script under Xvfb and require it
# to stay alive (window constructed) with a traceback-free stderr.
#
# Usage: scripts/smoke-launch.sh mv-mail mv-keychain mv-diskutil
#        SMOKE_ALLOW_EXIT=1 scripts/smoke-launch.sh mv-some-oneshot
#
# This catches the class of bug text-based suites cannot see: a broken
# window factory (e.g. passing a class-returning builder where an
# instance-producing factory is required) dies inside Gtk.Application's
# activate handler after import/unit tests already passed.
#
# Exit 0 = every requested app stayed up (or, with SMOKE_ALLOW_EXIT=1,
# exited cleanly); exit 1 = a launch failed.
# Prints a skip line and exits 0 when xvfb-run is unavailable.
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$REPO/packages/mavericks-apps/src/mavericks-apps/bin"
STAY="${SMOKE_STAY:-4}"
ALLOW_EXIT="${SMOKE_ALLOW_EXIT:-0}"
FAILURES=0

if ! command -v xvfb-run >/dev/null 2>&1; then
    echo "ok - smoke skipped (xvfb-run not installed)"
    exit 0
fi

if ! python3 -c "import gi" 2>/dev/null; then
    echo "ok - smoke skipped (PyGObject not installed)"
    exit 0
fi

# Apps import the shared runner from /usr/share/mavericks-apps first; when
# that install is absent (CI, fresh checkout) fall back to the repo copy.
export PYTHONPATH="$REPO/packages/mavericks-apps/src/mavericks-apps/lib${PYTHONPATH:+:$PYTHONPATH}"

for app in "$@"; do
    path="$BIN/$app"
    if [[ ! -f "$path" ]]; then
        echo "FAIL - smoke $app: script missing ($path)"
        FAILURES=$((FAILURES + 1))
        continue
    fi
    log="$(mktemp)"
    xvfb-run -a timeout $((STAY + 2)) python3 "$path" >"$log" 2>&1 &
    pid=$!
    sleep "$STAY"
    stayed=0
    if kill -0 "$pid" 2>/dev/null; then
        stayed=1
        kill "$pid" 2>/dev/null
    fi
    wait "$pid" 2>/dev/null

    if grep -q "Traceback" "$log"; then
        echo "FAIL - smoke $app: traceback during launch"
        sed -n '1,20p' "$log" | sed 's/^/      /'
        FAILURES=$((FAILURES + 1))
    elif [[ $stayed -eq 1 ]]; then
        echo "ok - smoke $app: stayed up ${STAY}s"
    elif [[ "$ALLOW_EXIT" == "1" ]]; then
        echo "ok - smoke $app: exited cleanly within ${STAY}s (oneshot allowed)"
    else
        echo "FAIL - smoke $app: died within ${STAY}s (no traceback)"
        sed -n '1,20p' "$log" | sed 's/^/      /'
        FAILURES=$((FAILURES + 1))
    fi
    rm -f "$log"
done

if [[ $FAILURES -gt 0 ]]; then
    echo "smoke: $FAILURES failure(s)"
    exit 1
fi
echo "ok - smoke launch: $*"
exit 0
