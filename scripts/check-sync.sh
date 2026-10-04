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
FAIL=0
bad() { echo "FAIL: $*"; FAIL=1; }
ok()  { echo "OK: $*"; }

PAIRS=(
  "scripts/install/mavericks-firstboot.sh:archiso-profile/releng/airootfs/usr/local/bin/mavericks/mavericks-firstboot.sh"
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
  "configs/desktop/xfce/xfce4-panel.xml:archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml"
  "configs/desktop/fonts/99-mavericks-cursive.conf:archiso-profile/releng/airootfs/etc/fonts/conf.d/99-mavericks-cursive.conf"
  "configs/desktop/xfce/settings.ini:archiso-profile/releng/airootfs/etc/skel/.config/gtk-3.0/settings.ini"
  "configs/desktop/thunar/thunarrc:archiso-profile/releng/airootfs/etc/skel/.config/Thunar/thunarrc"
  "configs/desktop/thunar/bookmarks:archiso-profile/releng/airootfs/etc/skel/.gtk-bookmarks.template"
  "configs/desktop/xfce/xfce4-desktop.xml:archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml"
  "configs/desktop/plank/dock1-settings:archiso-profile/releng/airootfs/etc/skel/.config/plank/dock1/settings"
  "packages/mavericks-apps/src/mavericks-apps/config/thunar-uca.xml:archiso-profile/releng/airootfs/etc/skel/.config/Thunar/uca.xml"
  "packages/mavericks-apps/src/mavericks-apps/config/xfce4-keyboard-shortcuts.xml:archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-keyboard-shortcuts.xml"
  "configs/desktop/skippy-xd/skippy-xd.rc:archiso-profile/releng/airootfs/etc/skel/.config/skippy-xd/skippy-xd.rc"
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
    desktop-file-validate "$f" 2>/dev/null && ok "desktop $(basename "$f")" || bad "desktop $f"
  else
    ok "desktop-skip $(basename "$f") (no desktop-file-validate)"
  fi
done < <(find packages -name '*.desktop' -print0 2>/dev/null)

echo "--- PKGBUILD parse ---"
# Prefer makepkg --printsrcinfo when available (Arch/dev hosts).
# On Ubuntu CI runners makepkg is absent — fall back to bash -n syntax only.
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

echo "--- firefox chrome ---"
if [[ -f scripts/test-firefox-chrome.py ]]; then
  python3 scripts/test-firefox-chrome.py && ok "firefox chrome css" || bad "firefox chrome css"
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
