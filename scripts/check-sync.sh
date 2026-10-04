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
  "configs/desktop/lightdm/lightdm.conf:archiso-profile/releng/airootfs/etc/lightdm/lightdm.conf"
  "configs/desktop/lightdm/lightdm-gtk-greeter.conf:archiso-profile/releng/airootfs/etc/lightdm/lightdm-gtk-greeter.conf"
  "configs/desktop/plank/dock1-settings:archiso-profile/releng/airootfs/etc/skel/.config/plank/dock1/settings"
  "packages/mavericks-apps/src/mavericks-apps/config/thunar-uca.xml:archiso-profile/releng/airootfs/etc/skel/.config/Thunar/uca.xml"
  "packages/mavericks-apps/src/mavericks-apps/config/xfce4-keyboard-shortcuts.xml:archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-keyboard-shortcuts.xml"
  "configs/desktop/skippy-xd/skippy-xd.rc:archiso-profile/releng/airootfs/etc/skel/.config/skippy-xd/skippy-xd.rc"
  "configs/network/99-mavericks.conf:archiso-profile/releng/airootfs/etc/NetworkManager/conf.d/99-mavericks.conf"
  "configs/network/99-mavericks-wifi-backend.conf:archiso-profile/releng/airootfs/etc/NetworkManager/conf.d/99-mavericks-wifi-backend.conf"
  "configs/profiles/fragments/99-mavericks-s3x.conf:archiso-profile/releng/airootfs/usr/local/share/mavericks/profiles/fragments/99-mavericks-s3x.conf"
  "configs/profiles/fragments/99-mavericks-display.conf:archiso-profile/releng/airootfs/usr/local/share/mavericks/profiles/fragments/99-mavericks-display.conf"
  "configs/power/99-mavericks-power.conf:archiso-profile/releng/airootfs/etc/tlp.d/99-mavericks-power.conf"
  "archiso-profile/releng/airootfs/etc/mkinitcpio.conf.d/99-mavericks-spi.conf:archiso-profile/releng/airootfs/etc/mkinitcpio.conf.d/99-mavericks-spi.conf"
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
for d in packages/*/; do
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

echo "--- P1-M1 firefox seed: profiles.ini activates mavericks.default ---"
python3 - <<'PYEOF' && ok "firefox seed profiles.ini" || bad "firefox seed profiles.ini"
import configparser, sys
from pathlib import Path
seed = Path("archiso-profile/releng/airootfs/etc/skel/.mozilla/firefox")
cp = configparser.ConfigParser()
cp.read(seed / "profiles.ini")
assert cp.has_section("Profile0"), "missing [Profile0]"
p = cp["Profile0"]
assert p.get("Path") == "mavericks.default", f"Path={p.get('Path')!r}"
assert p.get("IsRelative") == "1", "IsRelative must be 1"
assert p.get("Default") == "1", "Default=1 required for deterministic activation"
assert (seed / "mavericks.default" / "user.js").is_file(), "seed profile missing user.js"
ip = configparser.ConfigParser()
ip.read(seed / "installs.ini")
assert any(ip[s].get("Default") == "mavericks.default" for s in ip.sections()), \
    "installs.ini has no Default=mavericks.default"
PYEOF

echo "--- P0-J1 security: sshd off + root locked + no permissive override ---"
AIROOT="archiso-profile/releng/airootfs"
if [[ -e "$AIROOT/etc/systemd/system/multi-user.target.wants/sshd.service" ]]; then
  bad "sshd.service still enabled in ISO (multi-user.target.wants)"
else
  ok "sshd not enabled in ISO"
fi
if [[ -e "$AIROOT/etc/ssh/sshd_config.d/10-archiso.conf" ]]; then
  bad "permissive sshd_config.d/10-archiso.conf still present"
else
  ok "no permissive sshd_config override"
fi
ROOT_FIELD="$(grep '^root:' "$AIROOT/etc/shadow" 2>/dev/null | cut -d: -f2)"
if [[ "$ROOT_FIELD" == "!"* ]]; then
  ok "root password locked in ISO shadow"
else
  bad "root password not locked in ISO shadow (field='${ROOT_FIELD}')"
fi
if grep -q "passwd -l root" scripts/install/mavericks-firstboot.sh; then
  ok "firstboot locks root (installed system)"
else
  bad "firstboot missing passwd -l root"
fi
if grep -q "systemctl enable --now sshd" lab/agent/install.sh; then
  ok "lab agent install is the explicit sshd opt-in"
else
  bad "lab agent install missing explicit sshd enable"
fi
# sshd must not be in the boot critical path: no unit Wants/Requires it
# (explicit symlink walk: grep -r does not follow symlinks during recursion)
sshd_ref=0
for d in "$AIROOT/etc/systemd/system/"*.wants "$AIROOT/etc/systemd/system/"*.requires; do
  [[ -d "$d" ]] || continue
  for l in "$d"/*; do
    [[ -L "$l" ]] || continue
    tgt="$(readlink "$l")"
    if [[ "$tgt" == *sshd* ]]; then
      bad "sshd referenced by $l -> $tgt"
      sshd_ref=1
    fi
  done
done
[[ $sshd_ref -eq 0 ]] && ok "sshd not in boot critical path"

if [[ $FAIL -eq 0 ]]; then echo "ALL CHECKS PASSED"; else echo "CHECKS FAILED"; fi
exit $FAIL
