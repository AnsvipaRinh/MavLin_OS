#!/usr/bin/env bash
# mavericks-firstboot.sh — run ONCE after install (as root)
# Auto-detects hardware profile (generic vs macbook10,1) and applies config.
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

# --- 0. Profile selection (auto-detect + manual override) ---
log "0/10 profile selection"
"$REPO_DIR/scripts/install/mavericks-profile-select.sh"
PROFILE_CONF="/etc/mavericks/profile.conf"
if [[ ! -f "$PROFILE_CONF" ]]; then
    log "ERROR: profile config not found at $PROFILE_CONF"
    exit 1
fi
source "$PROFILE_CONF"
log "Active profile: $MAVERICKS_PROFILE (model: $MAVERICKS_MODEL)"

# --- 1. hostname/locale/time ---
log "1/10 hostname/locale/time"
hostnamectl set-hostname mavericks-macbook 2>/dev/null || echo mavericks-macbook > /etc/hostname
ln -sf /usr/share/zoneinfo/Europe/Berlin /etc/localtime 2>/dev/null || true
hwclock --systohc 2>/dev/null || true

# --- 2. bootloader cmdline (compose from profile) ---
log "2/10 bootloader cmdline"
BASE_CMDLINE="quiet loglevel=3"
FRAGMENT_DIR="$REPO_DIR/configs/profiles/fragments"
MACBOOK_FRAGMENTS=()
# MacBook fragments only applied if profile is macbook10,1 AND fragment files exist
if [[ "$MAVERICKS_PROFILE" == "macbook10,1" ]]; then
    [[ -f "$FRAGMENT_DIR/99-mavericks-s3x.conf" ]] && MACBOOK_FRAGMENTS+=("$(cat "$FRAGMENT_DIR/99-mavericks-s3x.conf" | grep -v '^#' | tr -d '\n')")
    [[ -f "$FRAGMENT_DIR/99-mavericks-display.conf" ]] && MACBOOK_FRAGMENTS+=("$(cat "$FRAGMENT_DIR/99-mavericks-display.conf" | grep -v '^#' | tr -d '\n')")
fi
FINAL_CMDLINE="$BASE_CMDLINE"
for frag in "${MACBOOK_FRAGMENTS[@]}"; do
  [[ -n "$frag" ]] && FINAL_CMDLINE="$FINAL_CMDLINE $frag"
done
log "Composed cmdline: $FINAL_CMDLINE"
for f in /boot/loader/entries/*.conf; do
  [[ -f "$f" ]] || continue
  if grep -q "^options" "$f"; then
    sed -i -E "s/^(options +.*rootflags=[^ ]+ *) .*/\1 $FINAL_CMDLINE/" "$f" || true
  fi
done
grep -H "^options" /boot/loader/entries/*.conf || true

# --- 3. TLP (generic + profile-specific fragment) ---
log "3/10 TLP"
# Generic baseline (always)
install -Dm644 "$REPO_DIR/configs/profiles/generic/99-mavericks-tlp.conf" /etc/tlp.d/99-mavericks.conf
# Profile-specific power tuning (MacBook10,1 only)
if [[ "$MAVERICKS_PROFILE" == "macbook10,1" ]]; then
    install -Dm644 "$REPO_DIR/archiso-profile/releng/airootfs/etc/tlp.d/99-mavericks-power.conf" /etc/tlp.d/99-mavericks-power.conf
else
    rm -f /etc/tlp.d/99-mavericks-power.conf
fi
rm -f /etc/tlp.d/10-experiment.conf
systemctl enable tlp.service

# --- 4. zram (structural, always on) ---
log "4/10 zram"
install -Dm644 "$REPO_DIR/configs/profiles/generic/99-mavericks-zram.conf" /etc/systemd/zram-generator.conf.d/99-mavericks.conf
systemctl enable systemd-zram-setup@zram0.service
# No sysctl overrides in baseline (kernel defaults). Remove stale file if present.
rm -f /etc/sysctl.d/99-mavericks.conf

# --- 5. network: NetworkManager (generic + MacBook wifi backend) ---
log "5/10 network"
# Generic connectivity tuning (always)
install -Dm644 "$REPO_DIR/configs/profiles/generic/99-mavericks-network.conf" /etc/NetworkManager/conf.d/99-mavericks.conf
# MacBook Wi-Fi backend pin (only on MacBook10,1 path)
if [[ "$MAVERICKS_PROFILE" == "macbook10,1" ]]; then
    install -Dm644 "$REPO_DIR/archiso-profile/releng/airootfs/etc/NetworkManager/conf.d/99-mavericks-wifi-backend.conf" /etc/NetworkManager/conf.d/99-mavericks-wifi-backend.conf
else
    rm -f /etc/NetworkManager/conf.d/99-mavericks-wifi-backend.conf
fi
systemctl disable --now iwd.service 2>/dev/null || true
systemctl disable --now systemd-networkd.service 2>/dev/null || true
systemctl enable NetworkManager.service
systemctl enable systemd-resolved.service 2>/dev/null || true
systemctl mask ModemManager.service 2>/dev/null || true
systemctl disable sshd.service reflector.service 2>/dev/null || true
# Security (P0-J1): lock root on the installed system
passwd -l root 2>/dev/null || true

# --- 6. modprobe (generic baseline) ---
log "6/10 modprobe"
install -Dm644 "$REPO_DIR/configs/profiles/generic/99-mavericks-modprobe.conf" /etc/modprobe.d/99-mavericks.conf

# --- 7. SPI/applespi (MacBook10,1 only, Strategy 1/2/3) ---
log "7/10 SPI/applespi"
if [[ "$MAVERICKS_PROFILE" == "macbook10,1" ]] && [[ -f "$REPO_DIR/archiso-profile/releng/airootfs/etc/mkinitcpio.conf.d/99-mavericks-spi.conf" ]]; then
    install -Dm644 "$REPO_DIR/archiso-profile/releng/airootfs/etc/mkinitcpio.conf.d/99-mavericks-spi.conf" /etc/mkinitcpio.conf.d/99-mavericks-spi.conf
    log "SPI fragment installed (Strategy 1/2/3 assumed — verify with apply-hardware-selection.sh)"
else
    rm -f /etc/mkinitcpio.conf.d/99-mavericks-spi.conf
    log "SPI fragment NOT installed (generic profile or Strategy 4 = external USB-C input)"
fi

# --- 8. Audio softvol (MacBook10,1 only, when macbook12-audio-driver present) ---
log "8/10 audio softvol"
if [[ "$MAVERICKS_PROFILE" == "macbook10,1" ]] && pacman -Q macbook12-audio-driver &>/dev/null; then
    if [[ -f "$REPO_DIR/packages/macbook12-audio-driver/51-macbook-cs4208-softvol.conf" ]]; then
        install -Dm644 "$REPO_DIR/packages/macbook12-audio-driver/51-macbook-cs4208-softvol.conf" /etc/wireplumber/main.lua.d/51-macbook-cs4208-softvol.conf
        log "WirePlumber softvol rule installed"
    fi
else
    rm -f /etc/wireplumber/main.lua.d/51-macbook-cs4208-softvol.conf
fi

# --- 9. NVRAM provisioning (MacBook10,1 only) ---
log "9/10 NVRAM provisioning"
if [[ "$MAVERICKS_PROFILE" == "macbook10,1" ]]; then
    "$REPO_DIR/scripts/install/extract-brcmfmac-nvram.sh" || true
else
    log "Skipped (generic profile)"
fi

# --- 10. desktop + firefox skel + local packages ---
log "10/10 desktop + packages"
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

# Local app/theme packages (mavericks-apps, mavericks-theme)
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