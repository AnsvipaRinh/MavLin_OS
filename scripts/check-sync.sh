#!/usr/bin/env bash
# check-sync.sh — pre-commit gate for the Mavericks Linux repo.
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
  "tools/experiments/mv-experiment.sh:archiso-profile/releng/airootfs/usr/local/bin/mavericks/mv-experiment.sh"
  "configs/profiles/baseline.conf:archiso-profile/releng/airootfs/usr/local/share/mavericks/profiles/baseline.conf"
  "configs/profiles/bootstrap.conf:archiso-profile/releng/airootfs/usr/local/share/mavericks/profiles/bootstrap.conf"
  "configs/profiles/diagnostic.conf:archiso-profile/releng/airootfs/usr/local/share/mavericks/profiles/diagnostic.conf"
  "configs/profiles/production.conf:archiso-profile/releng/airootfs/usr/local/share/mavericks/profiles/production.conf"
  "configs/profiles/recovery.conf:archiso-profile/releng/airootfs/usr/local/share/mavericks/profiles/recovery.conf"
  "configs/firefox/user.js:archiso-profile/releng/airootfs/etc/firefox/user.js"
  "configs/firefox/user.js:archiso-profile/releng/airootfs/etc/skel/.mozilla/firefox/mavericks.default/user.js"
  "configs/firefox/policies.json:archiso-profile/releng/airootfs/usr/lib/firefox/distribution/policies.json"
  "configs/firefox/chrome/userChrome.css:archiso-profile/releng/airootfs/etc/skel/.mozilla/firefox/mavericks.default/chrome/userChrome.css"
  "configs/firefox/chrome/userContent.css:archiso-profile/releng/airootfs/etc/skel/.mozilla/firefox/mavericks.default/chrome/userContent.css"
  "configs/desktop/xfce/xsettings.xml:archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml"
  "configs/desktop/xfce/xfwm4.xml:archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml"
  "configs/desktop/xfce/xfce4-panel.xml:archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml"
  "configs/desktop/xfce/terminalrc:archiso-profile/releng/airootfs/etc/skel/.config/xfce4/terminal/terminalrc"
  "configs/desktop/fonts/99-mavericks-cursive.conf:archiso-profile/releng/airootfs/etc/fonts/conf.d/99-mavericks-cursive.conf"
  "configs/desktop/xfce/settings.ini:archiso-profile/releng/airootfs/etc/skel/.config/gtk-3.0/settings.ini"
  "configs/desktop/thunar/thunarrc:archiso-profile/releng/airootfs/etc/skel/.config/Thunar/thunarrc"
  "configs/desktop/thunar/bookmarks:archiso-profile/releng/airootfs/etc/skel/.gtk-bookmarks.template"
  "configs/desktop/lightdm/lightdm.conf:archiso-profile/releng/airootfs/etc/lightdm/lightdm.conf"
  "configs/desktop/lightdm/lightdm-gtk-greeter.conf:archiso-profile/releng/airootfs/etc/lightdm/lightdm-gtk-greeter.conf"
  "configs/desktop/plank/dock1-settings:archiso-profile/releng/airootfs/etc/skel/.config/plank/dock1/settings"
  "packages/mavericks-apps/src/mavericks-apps/config/thunar-uca.xml:archiso-profile/releng/airootfs/etc/skel/.config/Thunar/uca.xml"
  "packages/mavericks-apps/src/mavericks-apps/config/xfce4-keyboard-shortcuts.xml:archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-keyboard-shortcuts.xml"
  "configs/desktop/skippy-xd/skippy-xd.rc:archiso-profile/releng/airootfs/etc/skel/.config/skippy-xd/skippy-xd.rc"
  "configs/network/99-mavericks.conf:archiso-profile/releng/airootfs/etc/NetworkManager/conf.d/99-mavericks.conf"
)
for pair in "${PAIRS[@]}"; do
  a="${pair%%:*}"; b="${pair##*:}"
  if [[ ! -f "$a" ]]; then bad "missing source $a"; continue; fi
  if [[ ! -f "$b" ]]; then bad "missing mirror $b"; continue; fi
  diff -q "$a" "$b" >/dev/null 2>&1 && ok "sync $(basename "$a")" || bad "diverged $a <> $b"
done

echo "--- shell syntax ---"
while IFS= read -r -d '' f; do
  bash -n "$f" 2>/dev/null && ok "bash $f" || bad "bash syntax $f"
done < <(find scripts tools packages archiso-profile configs -name "*.sh" -print0 2>/dev/null)
for f in scripts/apply-hardware-selection.sh scripts/build-local-pkgs.sh scripts/check-sync.sh \
         packages/mavericks-theme/PKGBUILD packages/epiphany-mavericks-theme/PKGBUILD \
         packages/mavericks-theme/mavericks-theme.install packages/epiphany-mavericks-theme/epiphany-mavericks-theme.install; do
  bash -n "$f" 2>/dev/null && ok "bash $f" || bad "bash syntax $f"
done

echo "--- python (shebang-gated) ---"
PYFAIL=0
while IFS= read -r -d '' f; do
  head -n 1 "$f" | grep -q "python3" || continue
  python3 -m py_compile "$f" 2>/dev/null || { bad "py_compile $f"; PYFAIL=1; }
done < <(find packages/mavericks-apps/src -type f -print0 2>/dev/null)
while IFS= read -r -d '' f; do
  head -n 1 "$f" | grep -q "python3" || continue
  python3 -m py_compile "$f" 2>/dev/null || { bad "py_compile $f"; PYFAIL=1; }
done < <(find scripts/bench -type f -name "*.py" -print0 2>/dev/null)
[[ $PYFAIL -eq 0 ]] && ok "py_compile all mv-* + bench"
find packages scripts -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

echo "--- xml ---"
while IFS= read -r -d '' f; do
  xmllint --noout "$f" 2>/dev/null && ok "xml $f" || bad "xml $f"
done < <(find packages archiso-profile -name "*.xml" -print0 2>/dev/null)

echo "--- desktop files ---"
while IFS= read -r -d '' f; do
  desktop-file-validate "$f" 2>/dev/null && ok "desktop $(basename "$f")" || bad "desktop $f"
done < <(find packages -name "*.desktop" -print0 2>/dev/null)

echo "--- PKGBUILD parse ---"
for d in packages/mavericks-apps packages/mavericks-theme packages/epiphany-mavericks-theme; do
  (cd "$d" && makepkg --printsrcinfo >/dev/null 2>&1) && ok "pkgbuild $d" || bad "pkgbuild $d"
done

if [[ "${1:-}" == "--check-repos" ]]; then
  echo "--- ISO package list vs repos ---"
  while read -r pkg; do
    [[ "$pkg" =~ ^#.*$ || -z "$pkg" || "$pkg" == mavericks-* ]] && continue
    pacman -Si "$pkg" >/dev/null 2>&1 || bad "package not in repos: $pkg"
  done < archiso-profile/releng/packages.x86_64
  ok "repo check done"
fi

echo "--- user.js syntax (no duplicate keys) ---"
python3 - <<'PYEOF' && ok "user.js no-dup-keys" || bad "user.js duplicate keys"
import re, sys
from pathlib import Path
for path in ["configs/firefox/user.js", "archiso-profile/releng/airootfs/etc/firefox/user.js"]:
    seen = {}
    for i, line in enumerate(Path(path).read_text().splitlines(), 1):
        m = re.match(r'user_pref\("([^"]+)"', line)
        if m:
            key = m.group(1)
            if key in seen:
                print(f"DUPLICATE: {key} at {path}:{i} (first at {path}:{seen[key]})", file=sys.stderr)
                sys.exit(1)
            seen[key] = i
PYEOF

echo "--- policies.json validity ---"
python3 - <<'PYEOF' && ok "policies.json valid" || bad "policies.json invalid"
import json, sys
from pathlib import Path
for path in ["configs/firefox/policies.json", "archiso-profile/releng/airootfs/usr/lib/firefox/distribution/policies.json"]:
    data = json.loads(Path(path).read_text())
    assert "policies" in data, f"missing 'policies' key in {path}"
    pol = data["policies"]
    assert "DisableTelemetry" in pol, f"missing DisableTelemetry in {path}"
    assert "ExtensionSettings" in pol, f"missing ExtensionSettings in {path}"
    es = pol["ExtensionSettings"]
    assert "*" in es and es["*"]["installation_mode"] == "blocked", f"missing * block in {path}"
    assert "uBlock0@raymondhill.net" in es, f"missing uBO allow in {path}"
PYEOF

echo "--- firefox chrome css ---"
python3 scripts/test-firefox-chrome.py && ok "firefox chrome css" || bad "firefox chrome css"

if [[ $FAIL -eq 0 ]]; then echo "ALL CHECKS PASSED"; else echo "CHECKS FAILED"; fi
exit $FAIL
