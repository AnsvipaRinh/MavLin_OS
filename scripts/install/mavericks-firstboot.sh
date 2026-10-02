#!/usr/bin/env bash
# mavericks-firstboot.sh — run ONCE after install on MacBook10,1 (as root)
# Applies Phase 0.3 baseline, installs desktop/firefox configs, enables services.
# Idempotent. Reboot after.
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
# firstboot runs from a repo checkout (cloned to the installed system or the
# live ISO build host). Fall back to well-known checkout locations; fail fast
# with a clear message instead of dying obscurely mid-script.
if [[ ! -d "$REPO_DIR/archiso-profile" ]]; then
  for cand in /root/macbook12-macos-linux /usr/local/src/macbook12-macos-linux; do
    if [[ -d "$cand/archiso-profile" ]]; then REPO_DIR="$cand"; break; fi
  done
fi
if [[ ! -d "$REPO_DIR/archiso-profile" ]]; then
  echo "[firstboot] ERROR: repo checkout not found."
  echo "[firstboot] Clone the repo (e.g. to /root/macbook12-macos-linux) and re-run."
  exit 1
fi
log() { echo "[firstboot] $*"; }

log "1/7 hostname/locale/time"
hostnamectl set-hostname mavericks-macbook 2>/dev/null || echo mavericks-macbook > /etc/hostname
ln -sf /usr/share/zoneinfo/Europe/Berlin /etc/localtime 2>/dev/null || true
hwclock --systohc 2>/dev/null || true

log "2/7 bootloader entries = baseline CMDLINE (base + fragments)"
# Base cmdline (generic, always applied)
BASE_CMDLINE="quiet loglevel=3"
# MacBook-specific fragments (graceful-missing: only append if file exists)
FRAGMENT_DIR="$REPO_DIR/configs/profiles/fragments"
MACBOOK_FRAGMENTS=()
[[ -f "$FRAGMENT_DIR/99-mavericks-s3x.conf" ]] && MACBOOK_FRAGMENTS+=("$(cat "$FRAGMENT_DIR/99-mavericks-s3x.conf" | grep -v '^#' | tr -d '\n')")
[[ -f "$FRAGMENT_DIR/99-mavericks-display.conf" ]] && MACBOOK_FRAGMENTS+=("$(cat "$FRAGMENT_DIR/99-mavericks-display.conf" | grep -v '^#' | tr -d '\n')")
# Compose final cmdline
FINAL_CMDLINE="$BASE_CMDLINE"
for frag in "${MACBOOK_FRAGMENTS[@]}"; do
  [[ -n "$frag" ]] && FINAL_CMDLINE="$FINAL_CMDLINE $frag"
done
log "Composed cmdline: $FINAL_CMDLINE"
for f in /boot/loader/entries/*.conf; do
  [[ -f "$f" ]] || continue
  if grep -q "^options" "$f"; then
    # preserve root= PARTUUID lines, replace trailing options after 'rw '
    sed -i -E "s/^(options +.*rootflags=[^ ]+ *) .*/\1 $FINAL_CMDLINE/" "$f" || true
  fi
done
grep -H "^options" /boot/loader/entries/*.conf || true

log "3/7 TLP baseline (generic + MacBook fragment)"
install -Dm644 "$REPO_DIR/archiso-profile/releng/airootfs/etc/tlp.d/99-mavericks.conf" /etc/tlp.d/99-mavericks.conf
install -Dm644 "$REPO_DIR/archiso-profile/releng/airootfs/etc/tlp.d/99-mavericks-power.conf" /etc/tlp.d/99-mavericks-power.conf
rm -f /etc/tlp.d/10-experiment.conf
systemctl enable tlp.service

log "4/7 zram"
install -Dm644 "$REPO_DIR/archiso-profile/releng/airootfs/etc/systemd/zram-generator.conf.d/99-mavericks.conf" /etc/systemd/zram-generator.conf.d/99-mavericks.conf
systemctl enable systemd-zram-setup@zram0.service
# No sysctl overrides in baseline (kernel defaults). Remove stale file if present.
rm -f /etc/sysctl.d/99-mavericks.conf

log "5/7 network: NetworkManager owns Wi-Fi on installed system"
# NM tuning: connectivity-check off (generic) + wpa_supplicant backend (MacBook fragment)
install -Dm644 "$REPO_DIR/archiso-profile/releng/airootfs/etc/NetworkManager/conf.d/99-mavericks.conf" /etc/NetworkManager/conf.d/99-mavericks.conf
install -Dm644 "$REPO_DIR/archiso-profile/releng/airootfs/etc/NetworkManager/conf.d/99-mavericks-wifi-backend.conf" /etc/NetworkManager/conf.d/99-mavericks-wifi-backend.conf
systemctl disable --now iwd.service 2>/dev/null || true
systemctl disable --now systemd-networkd.service 2>/dev/null || true
# NOTE: keep systemd-resolved enabled — /etc/resolv.conf points at its stub;
# disabling it would break DNS. NetworkManager cooperates with resolved.
systemctl enable NetworkManager.service
systemctl enable systemd-resolved.service 2>/dev/null || true
systemctl mask ModemManager.service 2>/dev/null || true
systemctl disable sshd.service reflector.service 2>/dev/null || true
# Security (P0-J1): lock root on the installed system (defense-in-depth; the
# ISO airootfs shadow is locked at packaging time). Remote bring-up is
# key-based SSH as the unprivileged mavericks-lab user (lab/agent/install.sh
# is the explicit opt-in that enables sshd) — never root login.
passwd -l root 2>/dev/null || true

log "6/8 take pre-change snapshot"
  # Pre-change snapshot hook for firstboot
  if command -v btrfs >/dev/null 2>&1 && mountpoint -q "/@snapshots"; then
    /usr/local/bin/mavericks/mv-snapshot-take "firstboot-$(date +%Y%m%d%H%M%S)" "Firstboot pre-change system snapshot"
  else
    log "WARN: not on btrfs filesystem, skipping snapshot for firstboot (logged)"
  fi
  
  log "7/8 enable fstrim timer"
  systemctl enable fstrim.timer 2>/dev/null || true
  log "8/8 desktop + firefox skel for new users"
  cp -r "$REPO_DIR/archiso-profile/releng/airootfs/etc/skel/." /etc/skel/
  install -Dm644 "$REPO_DIR/archiso-profile/releng/airootfs/etc/lightdm/lightdm.conf" /etc/lightdm/lightdm.conf
  install -Dm644 "$REPO_DIR/archiso-profile/releng/airootfs/etc/lightdm/lightdm-gtk-greeter.conf" /etc/lightdm/lightdm-gtk-greeter.conf
  install -Dm644 "$REPO_DIR/archiso-profile/releng/airootfs/usr/lib/firefox/distribution/policies.json" /usr/lib/firefox/distribution/policies.json
  # Thunar Finder surface for the invoking (live) user + bookmarks with real $HOME
  TARGET_USER="${SUDO_USER:-$(logname 2>/dev/null || true)}"
  if [[ -n "$TARGET_USER" && "$TARGET_USER" != "root" ]]; then
    UH=$(eval echo "~$TARGET_USER")
    mkdir -p "$UH/.config/Thunar"
    cp /etc/skel/.config/Thunar/thunarrc "$UH/.config/Thunar/thunarrc" 2>/dev/null || true
    cp /etc/skel/.config/Thunar/uca.xml "$UH/.config/Thunar/uca.xml" 2>/dev/null || true
    sed "s|USER_PLACEHOLDER|$TARGET_USER|g" /etc/skel/.gtk-bookmarks.template > "$UH/.gtk-bookmarks" 2>/dev/null || true
    mkdir -p "$UH/.config/xfce4/xfconf/xfce-perchannel-xml"
    cp /etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-keyboard-shortcuts.xml \
       "$UH/.config/xfce4/xfconf/xfce-perchannel-xml/" 2>/dev/null || true
    chown -R "$TARGET_USER:$(id -gn "$TARGET_USER")" "$UH/.config/Thunar" "$UH/.gtk-bookmarks" 2>/dev/null || true
    # Reminders hourly nudge (user timer, oneshot notify only)
    sudo -u "$TARGET_USER" systemctl --user enable mv-reminders-check.timer 2>/dev/null || true
    # Calendar upcoming-event nudge (user timer, oneshot notify only)
    sudo -u "$TARGET_USER" systemctl --user enable mv-calendar-check.timer 2>/dev/null || true
  fi
  systemctl enable lightdm.service
  systemctl enable bluetooth.service
  # Spotlight file index: without the plocate DB, Super+Space file search is
  # empty. Cheap daily oneshot (not a resident daemon).
  systemctl enable plocate-updatedb.timer
  # journald: persistent on installed system (ISO uses volatile)
  rm -f /etc/systemd/journald.conf.d/volatile-storage.conf 2>/dev/null || true
  
  log "9/9 NVRAM placeholder check + local app/theme packages"
  "$REPO_DIR/scripts/install/extract-brcmfmac-nvram.sh" || true
  # mavericks-apps/theme are NOT in upstream repos. Prefer nearby built package
  # files (ISO build output, checkout dir, live medium), then configured repo.
  LOCAL_PKGS=(mavericks-apps mavericks-theme)
  PKG_FILES=()
  for d in "$REPO_DIR/out" "$REPO_DIR" /run/archiso/bootmnt/mavericks /root; do
    for p in "${LOCAL_PKGS[@]}"; do
      for f in "$d"/"$p"-*.pkg.tar.zst; do
        [[ -f "$f" ]] && PKG_FILES+=("$f")
      done
    done
  done
  if (( ${#PKG_FILES[@]} )); then
    log "(installing local packages: ${PKG_FILES[*]})"
    pacman -U --needed --noconfirm "${PKG_FILES[@]}" || log "(local pkg install reported errors)"
  else
    pacman -Sy --needed --noconfirm "${LOCAL_PKGS[@]}" 2>/dev/null \
      || log "(mavericks-apps/theme NOT installed: no .pkg.tar.zst found and no [mavericks] repo; build with scripts/build-local-pkgs.sh)"
  fi
  log "Done. REBOOT, then run tools/diagnostics/mv-collect.sh as root."