#!/usr/bin/env bash
# mavericks-firstboot.sh — run ONCE after install on MacBook10,1 (as root)
# Applies Phase 0.3 baseline, installs desktop/firefox configs, enables services.
# Idempotent. Reboot after.
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
log() { echo "[firstboot] $*"; }

log "1/7 hostname/locale/time"
hostnamectl set-hostname mavericks-macbook 2>/dev/null || echo mavericks-macbook > /etc/hostname
ln -sf /usr/share/zoneinfo/Europe/Berlin /etc/localtime 2>/dev/null || true
hwclock --systohc 2>/dev/null || true

log "2/7 bootloader entries = baseline CMDLINE"
BASELINE_CDLINE="quiet loglevel=3 pcie_port_pm=off i915.enable_psr=0"
for f in /boot/loader/entries/*.conf; do
  [[ -f "$f" ]] || continue
  if grep -q "^options" "$f"; then
    # preserve root= PARTUUID lines, replace trailing options after 'rw '
    sed -i -E "s/^(options +.*rootflags=[^ ]+ *) .*/\1 $BASELINE_CDLINE/" "$f" || true
  fi
done
grep -H "^options" /boot/loader/entries/*.conf || true

log "3/7 TLP baseline"
install -Dm644 "$REPO_DIR/archiso-profile/releng/airootfs/etc/tlp.d/99-mavericks.conf" /etc/tlp.d/99-mavericks.conf
rm -f /etc/tlp.d/10-experiment.conf
systemctl enable tlp.service

log "4/7 zram"
install -Dm644 "$REPO_DIR/archiso-profile/releng/airootfs/etc/systemd/zram-generator.conf.d/99-mavericks.conf" /etc/systemd/zram-generator.conf.d/99-mavericks.conf
systemctl enable systemd-zram-setup@zram0.service
# No sysctl overrides in baseline (kernel defaults). Remove stale file if present.
rm -f /etc/sysctl.d/99-mavericks.conf

log "5/7 network: NetworkManager owns Wi-Fi on installed system"
systemctl disable --now iwd.service 2>/dev/null || true
systemctl disable --now systemd-networkd.service systemd-resolved.service 2>/dev/null || true
systemctl enable NetworkManager.service
systemctl mask ModemManager.service 2>/dev/null || true
systemctl disable sshd.service reflector.service 2>/dev/null || true

log "6/7 desktop + firefox skel for new users"
cp -r "$REPO_DIR/archiso-profile/releng/airootfs/etc/skel/." /etc/skel/
install -Dm644 "$REPO_DIR/archiso-profile/releng/airootfs/etc/lightdm/lightdm.conf" /etc/lightdm/lightdm.conf
install -Dm644 "$REPO_DIR/archiso-profile/releng/airootfs/etc/lightdm/lightdm-gtk-greeter.conf" /etc/lightdm/lightdm-gtk-greeter.conf
install -Dm644 "$REPO_DIR/archiso-profile/releng/airootfs/usr/lib/firefox/distribution/policies.json" /usr/lib/firefox/distribution/policies.json
systemctl enable lightdm.service
systemctl enable bluetooth.service
# journald: persistent on installed system (ISO uses volatile)
rm -f /etc/systemd/journald.conf.d/volatile-storage.conf 2>/dev/null || true

log "7/7 NVRAM placeholder check + theme packages"
"$REPO_DIR/scripts/install/extract-brcmfmac-nvram.sh" || true
pacman -Sy --needed --noconfirm mavericks-theme 2>/dev/null || log "(mavericks-theme: install from local repo/ISO)"
log "Done. REBOOT, then run tools/diagnostics/mv-collect.sh as root."
