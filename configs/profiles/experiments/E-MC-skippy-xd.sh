#!/usr/bin/env bash
# E-MC — Mission Control overview experiment (skippy-xd expose, one-shot).
# Baseline (default ISO): Super+Tab = rofi window mode (no new packages).
# Variant: Super+Tab = `skippy-xd` one-shot expose (real window overview).
# Energy model: NO daemon. `skippy-xd` with no arguments runs expose once and
# exits on select/Escape. Never enable --start-daemon (resident wakeups).
# Usage: ./E-MC-skippy-xd.sh [apply|revert|status]
#   apply  — needs skippy-xd installed (AUR: skippy-xd-git) + live Xfce session
#   revert — restore rofi window-mode binding
#   status — read-only: report package/binding/daemon state
set -euo pipefail
BACKUP_DIR="/var/lib/mavericks-experiments"
BACKUP_FILE="$BACKUP_DIR/mc-supertab.bak"
RC_SRC_USER="$HOME/.config/skippy-xd/skippy-xd.rc"
CHAN="xfce4-keyboard-shortcuts"
PROP="/commands/default/<Super>Tab"
BASELINE_CMD="rofi -show window -theme /usr/share/mavericks-apps/rofi-mavericks.rasi"
EXPOSE_CMD="skippy-xd"

need_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "missing: $1"; return 1; }; }

status() {
  echo "--- E-MC status (read-only) ---"
  if command -v skippy-xd >/dev/null 2>&1; then
    echo "package: present ($(skippy-xd --version 2>/dev/null || echo version-unknown))"
  else
    echo "package: ABSENT (install on HW: yay -S skippy-xd-git [AUR, GPL-2.0-or-later])"
  fi
  if pgrep -x skippy-xd >/dev/null 2>&1; then
    echo "daemon: RUNNING (unexpected — one-shot model wants no resident process)"
  else
    echo "daemon: not running (expected for one-shot model)"
  fi
  if need_cmd xfconf-query; then
    echo "Super+Tab now: $(xfconf-query -c "$CHAN" -p "$PROP" 2>/dev/null || echo UNSET)"
  else
    echo "binding: xfconf-query unavailable (no live Xfce session?)"
  fi
  [[ -f "$RC_SRC_USER" ]] && echo "user rc: $RC_SRC_USER present" \
    || echo "user rc: absent (ships in ISO skel for new users)"
}

apply() {
  command -v skippy-xd >/dev/null 2>&1 || {
    echo "E-MC apply refused: skippy-xd not installed."
    echo "On hardware with network: yay -S skippy-xd-git"
    echo "(pulls giflib, libjpeg-turbo, libxcomposite, libxdamage, libxext, libxft, libxinerama)"
    exit 1
  }
  need_cmd xfconf-query || { echo "E-MC apply refused: no live Xfce session."; exit 1; }
  mkdir -p "$BACKUP_DIR"
  xfconf-query -c "$CHAN" -p "$PROP" > "$BACKUP_FILE" 2>/dev/null \
    || echo "$BASELINE_CMD" > "$BACKUP_FILE"
  if [[ ! -f "$RC_SRC_USER" ]]; then
    mkdir -p "$(dirname "$RC_SRC_USER")"
    cp /etc/skel/.config/skippy-xd/skippy-xd.rc "$RC_SRC_USER"
    echo "deployed user rc from skel"
  fi
  xfconf-query -c "$CHAN" -p "$PROP" -s "$EXPOSE_CMD"
  echo "E-MC applied: Super+Tab -> skippy-xd (one-shot expose)."
  echo "Validate: press Super+Tab (windows fly out, no overlap), arrows+Return select, Escape cancels."
  echo "Revert: $0 revert"
}

revert() {
  need_cmd xfconf-query || { echo "E-MC revert refused: no live Xfce session."; exit 1; }
  if [[ -f "$BACKUP_FILE" ]]; then
    xfconf-query -c "$CHAN" -p "$PROP" -s "$(cat "$BACKUP_FILE")"
    rm -f "$BACKUP_FILE"
  else
    xfconf-query -c "$CHAN" -p "$PROP" -s "$BASELINE_CMD"
  fi
  echo "E-MC reverted: Super+Tab -> rofi window mode (baseline)."
}

case "${1:-status}" in
  apply) apply;; revert) revert;; status) status;;
  *) echo "Usage: $0 [apply|revert|status]"; exit 1;;
esac
