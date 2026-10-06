#!/usr/bin/env bash
# Manual GUI smoke for oid OS-power-trash-archive (not part of check-sync:
# check-sync is headless).  Run from the repo root:
#   bash lab/smoke-power-trash-archive.sh
# Every step is bounded with `timeout` so the smoke can never hang the
# caller on a dialog that would not map.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1
source "$REPO/scripts/gui-isolation.sh"
mv_gui_isolate || exit 1
mv_gui_pin_display || { echo "SKIP: no Xvfb"; exit 77; }
export HOME=/tmp/mvsmoke-home XDG_DATA_HOME=/tmp/mvsmoke-home/data
BIN=packages/mavericks-apps/src/mavericks-apps/bin
rm -rf /tmp/mvsmoke-home
mkdir -p "$XDG_DATA_HOME/Trash/files" "$XDG_DATA_HOME/Trash/info" /tmp/mvsmoke-home/orig
printf 'payload' > "$XDG_DATA_HOME/Trash/files/notes.txt"
printf '[Trash Info]\nPath=/tmp/mvsmoke-home/orig/notes.txt\nDeletionDate=2026-10-06T08:00:00\n' \
    > "$XDG_DATA_HOME/Trash/info/notes.txt.trashinfo"
mkdir -p /tmp/mvsmoke-home/src/sub && printf 'one' > /tmp/mvsmoke-home/src/a.txt \
    && printf 'two' > /tmp/mvsmoke-home/src/sub/b.txt
( cd /tmp/mvsmoke-home/src && tar czf /tmp/mvsmoke-home/demo.tar.gz a.txt sub )
fails=0

say() { printf '%s\n' "$*"; }
ok()  { printf 'ok   - %s\n' "$*"; }
no()  { printf 'FAIL - %s\n' "$*"; fails=$((fails+1)); }

# Escape a mapped window by id, then wait (bounded) for the process.
# The wait is always bounded: a dialog that refuses to close must not turn
# the smoke into a hang, and `wait` on a GUI child is exactly the thing
# that would.
dismiss() {
    local wid="$1"
    [ -n "$wid" ] && xdotool key --window "$wid" --clearmodifiers Escape 2>/dev/null
}

# reap $1, giving it at most $2 tenths of a second.
# A zombie still answers `kill -0`, so exit has to be read from
# /proc/<pid>/stat state 'Z' — otherwise this loop never terminates and the
# next iteration silently reuses the still-running Gtk.Application unique
# name (com.mavlinos.PowerUI), which is why only the first Power UI preset
# ever mapped.
running() {
    local st
    [ -d "/proc/$1" ] || return 1
    st=$(awk '{print $3}' "/proc/$1/stat" 2>/dev/null) || return 1
    [ "$st" != "Z" ]
}

reap() {
    local pid="$1" tries="${2:-100}"
    while running "$pid" && [ "$tries" -gt 0 ]; do
        sleep 0.1
        tries=$((tries-1))
    done
    wait "$pid" 2>/dev/null
    if running "$pid"; then
        kill -TERM "$pid" 2>/dev/null
        return 1
    fi
    return 0
}

say "--- Empty Trash: the alert must map and Escape must cancel ---"
"$BIN/mv-empty-trash" >/dev/null 2>&1 &
bg=$!
sleep 2.5
wid=$(xdotool search --class mv-empty-trash 2>/dev/null | tail -1)
if [ -n "$wid" ]; then ok "confirmation alert mapped"; else no "confirmation alert never mapped"; fi
dismiss "$wid"
reap "$bg" 150 || no "the confirmation dialog did not close on Escape"
left=$("$BIN/mv-empty-trash" --status)
case "$left" in
    *"1 item"*) ok "Escape cancelled: $left" ;;
    *)          no "Escape did not preserve the Trash: $left" ;;
esac

say "--- Put Back: trash:// URI restores to the original path ---"
if out=$(timeout 60 "$BIN/mv-trash-putback" "trash:///files/notes.txt" 2>&1) \
        && [ -f /tmp/mvsmoke-home/orig/notes.txt ]; then
    ok "$out"
else
    no "Put Back failed: $out"
fi

say "--- Archive Utility: demo.tar.gz expands into a folder called demo ---"
if out=$(timeout 120 "$BIN/mv-archive-utility" --quiet --no-open \
            /tmp/mvsmoke-home/demo.tar.gz 2>&1) \
        && [ -f /tmp/mvsmoke-home/demo/a.txt ] \
        && [ -f /tmp/mvsmoke-home/demo/sub/b.txt ]; then
    ok "expanded into demo/ with its nested structure intact"
else
    no "expansion failed: $out"
fi

say "--- Archive Utility: a corrupt archive must map its failure alert ---"
printf 'not an archive' > /tmp/mvsmoke-home/bad.zip
"$BIN/mv-archive-utility" --no-open /tmp/mvsmoke-home/bad.zip >/dev/null 2>&1 &
bg=$!
sleep 2.5
wid=$(xdotool search --class mv-archive-utility 2>/dev/null | tail -1)
if [ -n "$wid" ]; then ok "failure alert mapped"; else no "failure alert never mapped"; fi
dismiss "$wid"
reap "$bg" 150 || no "the failure alert did not close on Escape"
[ -d /tmp/mvsmoke-home/bad ] && no "a half-extracted folder was left behind" \
    || ok "no half-extracted folder left behind"

say "--- Power UI: chooser and all four presets must map a window ---"
for action in sleep restart shutdown logout; do
    "$BIN/mv-power-ui" "$action" >/dev/null 2>&1 &
    bg=$!
    sleep 2.5
    wid=$(xdotool search --class mv-power-ui 2>/dev/null | tail -1)
    geom=$(xdotool getwindowgeometry "$wid" 2>/dev/null \
           | sed -n 's/.*Geometry: \([0-9]*x[0-9]*\).*/\1/p')
    if [ -n "$wid" ] && [ -n "$geom" ]; then
        ok "$action preset mapped ($geom)"
    else
        no "$action preset never mapped"
    fi
    dismiss "$wid"
    reap "$bg" 150 || no "$action preset did not close on Escape"
done

say "--- host-display guard ---"
mv_gui_report || fails=$((fails+1))
say ""
if [ "$fails" -eq 0 ]; then say "smoke OK"; exit 0; fi
say "smoke FAILED ($fails)"; exit 1