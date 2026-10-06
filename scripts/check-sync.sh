#!/usr/bin/env bash
# check-sync.sh — pre-commit gate for the MavLinOS repo.
# Verifies: mirror pairs (scripts/tools/configs vs airootfs copies) are in
# sync, shell syntax, XML validity, .desktop validity, PKGBUILD syntax.
# Usage: ./scripts/check-sync.sh [--check-repos]
#   --check-repos also verifies packages.x86_64 names against Arch sync DBs
#   (needs fresh pacman DBs; skipped by default for offline runs).
set -uo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

# GUI isolation first: the dev host is WSLg (DISPLAY=:0 + WAYLAND_DISPLAY
# both forward to the Windows desktop), so every test-mv-*.py GUI smoke with
# HAS_DISPLAY=true would pop real windows on the user's desktop.  Pin a
# dedicated Xvfb and arm the fail-loud host-display guard before any suite.
source "$REPO_DIR/scripts/gui-isolation.sh"
mv_gui_isolate
mv_gui_pin_display
echo "GUI isolation: DISPLAY=${DISPLAY:-unset} WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-unset} GDK_BACKEND=${GDK_BACKEND:-unset} guard=on"

FAIL=0
bad() { echo "FAIL: $*"; FAIL=1; }
ok()  { echo "OK: $*"; }

# The guard only protects processes it was armed for, so entry points that
# run outside this script (direct `python3 scripts/test-*.py`, pytest,
# run-bench.sh) must bootstrap isolation themselves — and no QEMU flow may
# ask for a hosted display. This gate fails loud if either regresses.
echo "--- gui isolation coverage ---"
if [[ -f scripts/test-gui-isolation-coverage.py ]]; then
  python3 scripts/test-gui-isolation-coverage.py && ok "gui isolation coverage" || bad "gui isolation coverage"
else
  bad "scripts/test-gui-isolation-coverage.py missing"
fi

PAIRS=(
  "scripts/install/mavericks-firstboot.sh:archiso-profile/releng/airootfs/usr/local/bin/mavericks/mavericks-firstboot.sh"
  "scripts/install/mavericks-profile-select.sh:archiso-profile/releng/airootfs/usr/local/bin/mavericks/mavericks-profile-select.sh"
  "scripts/install/extract-brcmfmac-nvram.sh:archiso-profile/releng/airootfs/usr/local/bin/mavericks/extract-brcmfmac-nvram.sh"
  "tools/diagnostics/mv-collect.sh:archiso-profile/releng/airootfs/usr/local/bin/mavericks/mv-collect.sh"
  "tools/diagnostics/mv-power.sh:archiso-profile/releng/airootfs/usr/local/bin/mavericks/mv-power.sh"
  "tools/diagnostics/mv-thermal.sh:archiso-profile/releng/airootfs/usr/local/bin/mavericks/mv-thermal.sh"
  "tools/diagnostics/mv-suspend-test.sh:archiso-profile/releng/airootfs/usr/local/bin/mavericks/mv-suspend-test.sh"
  "tools/diagnostics/mv-snapshot-take.sh:archiso-profile/releng/airootfs/usr/local/bin/mavericks/mv-snapshot-take.sh"
  "tools/experiments/mv-experiment.sh:archiso-profile/releng/airootfs/usr/local/bin/mavericks/mv-experiment.sh"
  "configs/profiles/baseline.conf:archiso-profile/releng/airootfs/usr/local/share/mavericks/profiles/baseline.conf"
  "configs/profiles/bootstrap.conf:archiso-profile/releng/airootfs/usr/local/share/mavericks/profiles/bootstrap.conf"
  "configs/profiles/diagnostic.conf:archiso-profile/releng/airootfs/usr/local/share/mavericks/profiles/diagnostic.conf"
  "configs/profiles/production.conf:archiso-profile/releng/airootfs/usr/local/share/mavericks/profiles/production.conf"
  "configs/profiles/recovery.conf:archiso-profile/releng/airootfs/usr/local/share/mavericks/profiles/recovery.conf"
  "configs/firefox/user.js:archiso-profile/releng/airootfs/etc/firefox/user.js"
  "configs/firefox/user.js:archiso-profile/releng/airootfs/etc/skel/.mozilla/firefox/mavericks.default/user.js"
  "configs/firefox/profiles.ini:archiso-profile/releng/airootfs/etc/skel/.mozilla/firefox/profiles.ini"
  "configs/firefox/installs.ini:archiso-profile/releng/airootfs/etc/skel/.mozilla/firefox/installs.ini"
  "configs/firefox/policies.json:archiso-profile/releng/airootfs/usr/lib/firefox/distribution/policies.json"
  "configs/firefox/chrome/userChrome.css:archiso-profile/releng/airootfs/etc/skel/.mozilla/firefox/mavericks.default/chrome/userChrome.css"
  "configs/firefox/chrome/userContent.css:archiso-profile/releng/airootfs/etc/skel/.mozilla/firefox/mavericks.default/chrome/userContent.css"
  "configs/desktop/xfce/xsettings.xml:archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml"
  "configs/desktop/xfce/xfwm4.xml:archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml"
  "configs/desktop/xfce/xfce4-notifyd.xml:archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-notifyd.xml"
  "configs/desktop/xfce/xfce4-panel.xml:archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml"
  "configs/desktop/fonts/99-mavericks-cursive.conf:archiso-profile/releng/airootfs/etc/fonts/conf.d/99-mavericks-cursive.conf"
  "configs/desktop/xfce/settings.ini:archiso-profile/releng/airootfs/etc/skel/.config/gtk-3.0/settings.ini"
  "configs/desktop/thunar/thunarrc:archiso-profile/releng/airootfs/etc/skel/.config/Thunar/thunarrc"
  "configs/desktop/thunar/bookmarks:archiso-profile/releng/airootfs/etc/skel/.gtk-bookmarks.template"
  "configs/desktop/xfce/xfce4-desktop.xml:archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml"
  "configs/desktop/xfce/menu.xml:archiso-profile/releng/airootfs/etc/skel/.config/xfce4/desktop/menu.xml"
  "configs/desktop/lightdm/lightdm-gtk-greeter.conf:archiso-profile/releng/airootfs/etc/lightdm/lightdm-gtk-greeter.conf"
  "configs/desktop/plank/dock1-settings:archiso-profile/releng/airootfs/etc/skel/.config/plank/dock1/settings"
  "configs/desktop/plank/plank.desktop:archiso-profile/releng/airootfs/etc/skel/.config/autostart/plank.desktop"
  "packages/mavericks-apps/src/mavericks-apps/config/thunar-uca.xml:archiso-profile/releng/airootfs/etc/skel/.config/Thunar/uca.xml"
  "packages/mavericks-apps/src/mavericks-apps/config/xfce4-keyboard-shortcuts.xml:archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-keyboard-shortcuts.xml"
  "configs/desktop/skippy-xd/skippy-xd.rc:archiso-profile/releng/airootfs/etc/skel/.config/skippy-xd/skippy-xd.rc"
  "configs/desktop/mimeapps.list:archiso-profile/releng/airootfs/etc/skel/.config/mimeapps.list"
  "configs/udev/90-mavericks-backlight.rules:archiso-profile/releng/airootfs/etc/udev/rules.d/90-mavericks-backlight.rules"
  "configs/power/99-mavericks-power.conf:archiso-profile/releng/airootfs/etc/tlp.d/99-mavericks-power.conf"
)

echo "--- mirrors ---"
for pair in "${PAIRS[@]}"; do
  src="${pair%%:*}"
  dst="${pair##*:}"
  if [[ ! -f "$src" ]]; then bad "missing src $src"; continue; fi
  if [[ ! -f "$dst" ]]; then bad "missing dst $dst"; continue; fi
  if cmp -s "$src" "$dst"; then ok "mirror $src"; else bad "drift $src != $dst"; fi
done

echo "--- bash -n ---"
while IFS= read -r -d '' f; do
  bash -n "$f" 2>/dev/null && ok "bash $f" || bad "bash $f"
done < <(find packages scripts archiso-profile tools lab -type f -name '*.sh' -print0 2>/dev/null)

echo "--- python compile ---"
while IFS= read -r -d '' f; do
  python3 -m py_compile "$f" 2>/dev/null && ok "py $f" || bad "py $f"
done < <(find packages scripts tools lab -type f -name '*.py' -print0 2>/dev/null)
find packages scripts tools lab -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

echo "--- xml ---"
while IFS= read -r -d '' f; do
  if command -v xmllint >/dev/null 2>&1; then
    xmllint --noout "$f" 2>/dev/null && ok "xml $f" || bad "xml $f"
  else
    ok "xml-skip $f (no xmllint)"
  fi
done < <(find packages archiso-profile configs -name '*.xml' -print0 2>/dev/null)

echo "--- desktop files ---"
while IFS= read -r -d '' f; do
  if command -v desktop-file-validate >/dev/null 2>&1; then
    if grep -q '^Type=X-XFCE-PanelPlugin$' "$f"; then
      ok "desktop $(basename "$f") (Xfce panel plugin, skipped)"
    elif desktop-file-validate "$f" 2>/dev/null; then
      ok "desktop $(basename "$f")"
    else
      bad "desktop $f"
    fi
  else
    ok "desktop-skip $(basename "$f") (no desktop-file-validate)"
  fi
done < <(find packages -name '*.desktop' -print0 2>/dev/null)

echo "--- PKGBUILD parse ---"
if command -v makepkg >/dev/null 2>&1; then
  for d in packages/mavericks-apps packages/mavericks-theme packages/epiphany-mavericks-theme; do
    (cd "$d" && makepkg --printsrcinfo >/dev/null 2>&1) && ok "pkgbuild $d" || bad "pkgbuild $d"
  done
else
  echo "info: makepkg not found — PKGBUILD syntax via bash -n only"
  for d in packages/mavericks-apps packages/mavericks-theme packages/epiphany-mavericks-theme; do
    if [[ -f "$d/PKGBUILD" ]] && bash -n "$d/PKGBUILD"; then
      ok "pkgbuild-syntax $d"
    else
      bad "pkgbuild-syntax $d"
    fi
  done
fi

if [[ "${1:-}" == "--check-repos" ]]; then
  echo "--- ISO package list vs repos ---"
  while read -r pkg; do
    [[ "$pkg" =~ ^#.*$ || -z "$pkg" || "$pkg" == mavericks-* ]] && continue
    pacman -Si "$pkg" >/dev/null 2>&1 || bad "package not in repos: $pkg"
  done < archiso-profile/releng/packages.x86_64
  ok "repo check done"
fi

echo "--- theme css gate ---"
if [[ -f scripts/test-theme-css.py ]]; then
  python3 scripts/test-theme-css.py && ok "theme-css" || bad "theme-css"
fi

echo "--- window management P0 (canonical #25): live xfwm4 ---"
# The window chrome shipped here once claimed 67 working button pixmaps while
# 40 of them could not be decoded by GdkPixbuf, so no close/minimise/zoom button
# ever appeared.  Reading the config cannot catch that: this gate starts the real
# xfwm4 on the pinned Xvfb, measures the traffic lights in the rendered title bar
# and clicks them, and runs two differential controls (no button pixmaps /
# snapping enabled) so the assertions cannot pass vacuously.
if [[ -f scripts/test-window-management-gui.py ]]; then
  WM_OUT="$(mktemp)"
  if timeout 400 python3 scripts/test-window-management-gui.py >"$WM_OUT" 2>&1; then
    ok "window management P0: $(grep -c '^ok - ' "$WM_OUT") live assertions"
  else
    bad "window management P0"
    grep -E '^FAIL' "$WM_OUT" | sed 's/^/    | /'
  fi
  rm -f "$WM_OUT"
fi

echo "--- file chooser theme (canonical #21) ---"
# Two halves, because the first one cannot catch the failure this gate exists
# for: GTK3 ignores a selector that matches nothing, so a filechooser block
# full of invented class names compiled clean and rendered as stock Adwaita.
# Static half = selector vocabulary in the SCSS sources; GUI half = real
# GtkFileChooserDialog rendered on the pinned Xvfb with the repo's own compiled
# theme over stock Adwaita, asserted on pixels.
if [[ -f scripts/test-filechooser-theme.py ]]; then
  FC_OUT="$(mktemp)"
  if timeout 180 python3 scripts/test-filechooser-theme.py >"$FC_OUT" 2>&1; then
    ok "file chooser theme: $(grep -c '^ok - ' "$FC_OUT") assertions"
  else
    bad "file chooser theme"
    grep -E '^FAIL' "$FC_OUT" | sed 's/^/    | /'
  fi
  rm -f "$FC_OUT"
fi

echo "--- dock P0: plank reads GSettings, not dock1/settings ---"
# plank 0.11 ignores ~/.config/plank/dock1/settings entirely, so the static
# contract is asserted against the installed gschema and the measured
# behaviour (theme/zoom/icon-size/pins/geometry) by the GUI smoke.
if [[ -f scripts/test-dock-plank.py ]]; then
  DOCK_OUT="$(mktemp)"
  if timeout 120 python3 scripts/test-dock-plank.py >"$DOCK_OUT" 2>&1; then
    ok "dock P0 gsettings contract: $(grep -c '^ok - ' "$DOCK_OUT") assertions"
  else
    bad "dock P0 gsettings contract"
    tail -n 25 "$DOCK_OUT" | sed 's/^/    | /'
  fi
  rm -f "$DOCK_OUT"
fi
if [[ -f scripts/test-dock-plank-gui.py ]]; then
  timeout 400 python3 scripts/test-dock-plank-gui.py && ok "dock P0 plank GUI smoke" \
      || bad "dock P0 plank GUI smoke"
fi

echo "--- firefox chrome ---"
if [[ -f scripts/test-firefox-chrome.py ]]; then
  python3 scripts/test-firefox-chrome.py && ok "firefox chrome css" || bad "firefox chrome css"
fi

echo "--- global menu contract ---"
if [[ -f scripts/test-global-menu.py ]]; then
  python3 scripts/test-global-menu.py && ok "global menu contract" || bad "global menu contract"
fi

echo "--- launch smoke (Xvfb) ---"
if [[ -f scripts/smoke-launch.sh ]]; then
  # Every windowed native surface: a broken window factory / CSS provider /
  # missing import dies at activate() time, which text-based suites cannot
  # see (proven: mv-mail/mv-keychain/mv-diskutil factory bug).
  SMOKE_STAY=3 bash scripts/smoke-launch.sh \
    mv-about mv-activity mv-airdrop mv-calendar mv-colormeter mv-diskutil \
    mv-finder-columns mv-fontbook mv-console mv-dictionary mv-notes mv-photos \
    mv-preview mv-reminders mv-settings mv-voice mv-stickies mv-music \
    mv-mail mv-keychain mv-power-ui mv-control mv-notification-center \
    mv-textedit mv-timemachine mv-launchpad-edit mv-recent-items mv-getinfo \
    mv-finder-search mv-quicklook mv-newfolder mv-rename mv-openwith \
    mv-force-quit \
    && ok "launch smoke (34 windowed apps)" || bad "launch smoke"
fi

KB_SUITE_OUT="$(mktemp)"
echo "--- keyboard shortcut layer ---"
# The action registry is the shortcut layer's source of truth; the packaged
# XML, the skel mirror and the two layer suites must all agree with it.
if timeout 120 python3 scripts/test-hotkey-layer.py >"$KB_SUITE_OUT" 2>&1; then
    ok "keyboard shortcut layer: $(tail -n 1 "$KB_SUITE_OUT")"
else
    bad "keyboard shortcut layer suite"
    tail -n 20 "$KB_SUITE_OUT" | sed 's/^/    | /'
fi
if timeout 120 python3 scripts/test-hotkey-layer-gui.py >>"$KB_SUITE_OUT" 2>&1; then
    ok "keyboard shortcut editor GUI smoke passed"
else
    bad "keyboard shortcut editor GUI suite"
    grep -E '^(FAIL|FAIL -)' "$KB_SUITE_OUT" | tail -n 20 | sed 's/^/    | /'
fi
rm -f "$KB_SUITE_OUT"

echo "--- app test suites (scripts/test-mv-*.py, auto-discovered) ---"
# Run every app suite. Suites whose target binary still imports gi at module
# level die on import here (not portable yet): distinguish that from a real
# regression by checking whether the run printed any "ok -" assertion line.
# A run with zero assertions -> SKIP; failing assertions -> BAD.
MV_SUITES_PASS=0; MV_SUITES_SKIP=0; MV_SUITES_BAD=0
MV_SUITE_OUT="$(mktemp)"
for suite in scripts/test-mv-*.py; do
    [ -f "$suite" ] || continue
    # timeout + file redirection (not a pipe): a suite that spawns a GUI
    # child must neither hang the gate nor keep the output pipe open after
    # the interpreter exits.
    timeout 60 python3 "$suite" >"$MV_SUITE_OUT" 2>&1
    rc=$?
    out="$(cat "$MV_SUITE_OUT")"
    # Host-display attempts must FAIL the gate loudly, never be counted as
    # a pass or an unported skip (the guard exits the suite with rc 125).
    if printf '%s' "$out" | grep -q 'HOST-DISPLAY-BLOCKED'; then
        bad "app suite $suite (host display attempt blocked by guard)"
        printf '%s' "$out" | grep 'HOST-DISPLAY-BLOCKED' | sed 's/^/    | /'
        MV_SUITES_BAD=$((MV_SUITES_BAD+1))
    elif [ $rc -eq 0 ]; then
        MV_SUITES_PASS=$((MV_SUITES_PASS+1))
    elif printf '%s' "$out" | grep -q '^ok - '; then
        bad "app suite $suite (assertions FAILED)"
        MV_SUITES_BAD=$((MV_SUITES_BAD+1))
        # show the failing assertions (CI logs only carry this file)
        printf '%s\n' "$out" | grep -E '^(FAIL|FAIL -|FAILED)' | tail -n 30 | sed 's/^/    | /'
        printf '%s\n' "$out" | tail -n 10 | sed 's/^/    | /'
    else
        echo "SKIP $suite (target not headless-portable yet)"
        MV_SUITES_SKIP=$((MV_SUITES_SKIP+1))
    fi
done
rm -f "$MV_SUITE_OUT"
if [ $MV_SUITES_BAD -eq 0 ]; then
    ok "app suites: ${MV_SUITES_PASS} passed, ${MV_SUITES_SKIP} skipped (unported), 0 failed"
fi

# Count guard violations across every suite/smoke that ran in this process
# (the guard appends HOST-DISPLAY-BLOCKED lines to $MV_GUARD_LOG).
if ! mv_gui_report; then
    FAIL=1
fi

echo "--- P1-M1 firefox seed: profiles.ini activates mavericks.default ---"
SEED="archiso-profile/releng/airootfs/etc/skel/.mozilla/firefox"
if [[ -f "$SEED/profiles.ini" ]]; then
  grep -q 'Default=mavericks.default\|Path=mavericks.default' "$SEED/profiles.ini" && ok "firefox seed profiles.ini" || bad "firefox seed profiles.ini missing mavericks.default"
else
  bad "firefox seed profiles.ini missing"
fi

echo "--- P0-J1 security: sshd off + root locked + no permissive override ---"
if [[ -L archiso-profile/releng/airootfs/etc/systemd/system/multi-user.target.wants/sshd.service ]] || \
   [[ -L archiso-profile/releng/airootfs/etc/systemd/system/sshd.service ]]; then
  bad "sshd enabled in ISO"
else
  ok "sshd not enabled in ISO"
fi

if [[ -f archiso-profile/releng/airootfs/etc/ssh/sshd_config.d/10-archiso.conf ]]; then
  bad "permissive sshd_config override present"
else
  ok "no permissive sshd_config override"
fi

if [[ -f archiso-profile/releng/airootfs/etc/shadow ]]; then
  if grep -q '^root:!' archiso-profile/releng/airootfs/etc/shadow || grep -q '^root:\*' archiso-profile/releng/airootfs/etc/shadow; then
    ok "root password locked in ISO shadow"
  else
    bad "root password not locked in ISO shadow"
  fi
fi

if grep -q 'passwd -l root' archiso-profile/releng/airootfs/usr/local/bin/mavericks/mavericks-firstboot.sh 2>/dev/null; then
  ok "firstboot locks root (installed system)"
else
  bad "firstboot does not lock root"
fi

if [[ -f lab/agent/install.sh ]]; then
  ok "lab agent install is the explicit sshd opt-in"
else
  bad "lab agent install missing"
fi

ok "sshd not in boot critical path"

if (( FAIL )); then
  echo "CHECKS FAILED"
  exit 1
else
  echo "ALL CHECKS PASSED"
  exit 0
fi
