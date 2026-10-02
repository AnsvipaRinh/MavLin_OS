#!/usr/bin/env bash
# apply-hardware-selection.sh
# Автоматизация пост-установки на реальном железе MacBook10,1
# Запускать ПОСЛЕ первой загрузки установленной системы от root

set -euo pipefail

LOG_FILE="/var/log/mavericks-hardware-setup.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== Mavericks Linux Hardware Selection ==="
echo "Started: $(date)"
echo

# --- 1. Подтверждение модели ---
MODEL=$(dmidecode -s system-product-name 2>/dev/null || echo "unknown")
echo "Detected model: $MODEL"
if [[ "$MODEL" != "MacBook10,1" ]]; then
    echo "WARNING: Expected MacBook10,1, got $MODEL"
    echo "Update docs/HARDWARE.md and rebuild ISO if needed."
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    [[ ! $REPLY =~ ^[Yy]$ ]] && exit 1
fi

# --- 2. Wi-Fi ---
echo
echo "=== Wi-Fi Selection ==="
LSPCI_OUTPUT=$(lspci -nn -d 14e4: 2>/dev/null || true)
echo "Broadcom device: $LSPCI_OUTPUT"

if echo "$LSPCI_OUTPUT" | grep -q "14e4:43ba"; then
    REV=$(echo "$LSPCI_OUTPUT" | sed -n 's/.*rev \([0-9a-f]*\).*/\1/p' | head -1)
    echo "Detected BCM43602 revision: $REV"
    
    # MacBook10,1 typically has rev 03+ requiring broadcom-wl-dkms
    if [[ "$REV" =~ ^(03|04|05|06|07|08|09|0a|0b|0c|0d|0e|0f)$ ]]; then
        echo "→ Using broadcom-wl-dkms (revision 03+)"
        WIFI_DRIVER="broadcom-wl-dkms"
    else
        echo "→ Using brcmfmac (revision 01/02)"
        WIFI_DRIVER="brcmfmac"
    fi
else
    echo "No BCM43602 detected, defaulting to brcmfmac"
    WIFI_DRIVER="brcmfmac"
fi

# --- 3. Аудио ---
echo
echo "=== Audio Test ==="
if speaker-test -c 2 -t sine -f 440 -l 1 &>/dev/null; then
    echo "→ Audio works out of the box"
    AUDIO_DRIVER="none"
else
    echo "→ Built-in speakers silent, need macbook12-audio-driver"
    AUDIO_DRIVER="macbook12-audio-driver"
fi

# --- 4. Bluetooth ---
echo
echo "=== Bluetooth ==="
if btmgmt info 2>/dev/null | grep -q "controller"; then
    echo "→ Bluetooth controller detected"
    BT_DRIVER="in-kernel"
else
    echo "→ No controller found, need macbook12-bluetooth-driver"
    BT_DRIVER="macbook12-bluetooth-driver"
fi

# --- 5. applespi (клавиатура/трекпад) ---
echo
echo "=== applespi Keyboard/Trackpad ==="
if dmesg | grep -q "applespi"; then
    if dmesg | grep -q -i "timeout\|error\|fail"; then
        echo "→ applespi errors detected"
        echo "Select strategy:"
        echo "  1) macbook12-spi-driver-dkms (AUR) on linux-zen"
        echo "  2) linux-macbook kernel with applespi patches"
        echo "  3) linux-lts + backport patches"
        echo "  4) Skip (use external USB-C input)"
        read -p "Choice (1-4): " STRAT
        case $STRAT in
            1) SPI_DRIVER="macbook12-spi-driver-dkms" ;;
            2) SPI_DRIVER="linux-macbook" ;;
            3) SPI_DRIVER="linux-lts-applespi" ;;
            *) SPI_DRIVER="none"; echo "Using external USB-C input" ;;
        esac
    else
        echo "→ applespi loaded without errors"
        SPI_DRIVER="in-kernel"
    fi
else
    echo "→ applespi not loaded"
    SPI_DRIVER="none"
fi

# --- 6. Применение выборов ---
# NOTE (Phase 0.3): Wi-Fi driver choice is brcmfmac by default.
# broadcom-wl-dkms is an EXPERIMENT (often fails to build on modern kernels).
# Do NOT blacklist brcmfmac in baseline. NVRAM provisioned separately.
echo
echo "=== Applying Configuration ==="

PACKAGES_TO_INSTALL=()
PACKAGES_TO_REMOVE=()

# Wi-Fi — baseline brcmfmac; wl only if user explicitly chose experiment
if [[ "$WIFI_DRIVER" == "broadcom-wl-dkms" ]]; then
    echo "WARNING: broadcom-wl-dkms is EXPERIMENTAL (Phase 0.3 E-WIFI)."
    PACKAGES_TO_INSTALL+=("broadcom-wl-dkms")
elif [[ "$WIFI_DRIVER" == "brcmfmac" ]]; then
    PACKAGES_TO_INSTALL+=("linux-firmware")
fi

# Audio
if [[ "$AUDIO_DRIVER" == "macbook12-audio-driver" ]]; then
    PACKAGES_TO_INSTALL+=("macbook12-audio-driver")
fi

# Bluetooth
if [[ "$BT_DRIVER" == "macbook12-bluetooth-driver" ]]; then
    PACKAGES_TO_INSTALL+=("macbook12-bluetooth-driver" "bluez" "bluez-utils")
else
    PACKAGES_TO_INSTALL+=("bluez" "bluez-utils")
fi

# applespi
case $SPI_DRIVER in
    "macbook12-spi-driver-dkms")
        PACKAGES_TO_INSTALL+=("macbook12-spi-driver-dkms")
        ;;
    "linux-macbook")
        PACKAGES_TO_INSTALL+=("linux-macbook" "linux-macbook-headers")
        PACKAGES_TO_REMOVE+=("linux-zen" "linux-zen-headers")
        ;;
    "linux-lts-applespi")
        PACKAGES_TO_INSTALL+=("linux-lts" "linux-lts-headers")
        PACKAGES_TO_REMOVE+=("linux-zen" "linux-zen-headers")
        ;;
esac

# Always ensure base packages
PACKAGES_TO_INSTALL+=("mavericks-theme" "epiphany-mavericks-theme")

# Install packages
if [[ ${#PACKAGES_TO_INSTALL[@]} -gt 0 ]]; then
    echo "Installing: ${PACKAGES_TO_INSTALL[*]}"
    pacman -Sy --needed --noconfirm "${PACKAGES_TO_INSTALL[@]}"
fi

if [[ ${#PACKAGES_TO_REMOVE[@]} -gt 0 ]]; then
    echo "Removing: ${PACKAGES_TO_REMOVE[*]}"
    pacman -Rns --noconfirm "${PACKAGES_TO_REMOVE[@]}" 2>/dev/null || true
fi

# --- 7. Обновление конфигов ---
echo
echo "=== Updating Configs ==="

# Modprobe config — Phase 0.3 baseline: NO hardware overrides.
# i915/nvme/applespi use kernel defaults; experiments via configs/profiles/experiments/.
cat > /etc/modprobe.d/99-mavericks.conf <<EOF
# Auto-generated by apply-hardware-selection.sh on $(date)
# Phase 0.3 baseline: kernel defaults. No active options.
# Wi-Fi driver choice: $WIFI_DRIVER (brcmfmac = baseline, wl = experiment)
EOF

# Mkinitcpio modules — generic base; MacBook SPI modules in drop-in fragment
MKINITCPIO_MODULES=""
if [[ "$SPI_DRIVER" == "macbook12-spi-driver-dkms" ]]; then
    MKINITCPIO_MODULES="macbook12_spi"
fi
# Write fragment only if MacBook SPI modules needed (Strategies 1/2/3)
if [[ -n "$MKINITCPIO_MODULES" ]] || [[ "$SPI_DRIVER" == "in-kernel" ]]; then
    # Base SPI modules for in-kernel or linux-macbook/linux-lts-applespi
    if [[ "$SPI_DRIVER" == "in-kernel" ]] || [[ "$SPI_DRIVER" == "linux-macbook" ]] || [[ "$SPI_DRIVER" == "linux-lts-applespi" ]]; then
        MKINITCPIO_MODULES="applespi spi_pxa2xx_platform intel_lpss_pci intel_lpss_acpi $MKINITCPIO_MODULES"
    fi
    cat > /etc/mkinitcpio.conf.d/99-mavericks-spi.conf <<EOF
# Auto-generated by apply-hardware-selection.sh on $(date)
# MacBook10,1 SPI/applespi modules for Strategy: $SPI_DRIVER
# Graceful-missing: this file only installed when SPI driver selected.
MODULES=($MKINITCPIO_MODULES)
EOF
else
    # Strategy 4 (Skip) — remove fragment if present
    rm -f /etc/mkinitcpio.conf.d/99-mavericks-spi.conf
fi

# Bootloader entries — compose from base + fragments (graceful-missing)
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FRAGMENT_DIR="$REPO_DIR/configs/profiles/fragments"
BASE_CMDLINE="quiet loglevel=3"
MACBOOK_FRAGMENTS=()
[[ -f "$FRAGMENT_DIR/99-mavericks-s3x.conf" ]] && MACBOOK_FRAGMENTS+=("$(cat "$FRAGMENT_DIR/99-mavericks-s3x.conf" | grep -v '^#' | tr -d '\n')")
[[ -f "$FRAGMENT_DIR/99-mavericks-display.conf" ]] && MACBOOK_FRAGMENTS+=("$(cat "$FRAGMENT_DIR/99-mavericks-display.conf" | grep -v '^#' | tr -d '\n')")
FINAL_CMDLINE="$BASE_CMDLINE"
for frag in "${MACBOOK_FRAGMENTS[@]}"; do
  [[ -n "$frag" ]] && FINAL_CMDLINE="$FINAL_CMDLINE $frag"
done

if [[ "$SPI_DRIVER" == "linux-macbook" ]]; then
    cat > /boot/loader/entries/mavericks-linux-macbook.conf <<EOF
title   Mavericks Linux (linux-macbook)
linux   /vmlinuz-linux-macbook
initrd  /intel-ucode.img
initrd  /initramfs-linux-macbook.img
options root=PARTUUID=%ROOT_PARTUUID% rw rootflags=subvol=@ $FINAL_CMDLINE
EOF
elif [[ "$SPI_DRIVER" == "linux-lts-applespi" ]]; then
    cat > /boot/loader/entries/mavericks-linux-lts.conf <<EOF
title   Mavericks Linux (linux-lts)
linux   /vmlinuz-linux-lts
initrd  /intel-ucode.img
initrd  /initramfs-linux-lts.img
options root=PARTUUID=%ROOT_PARTUUID% rw rootflags=subvol=@ $FINAL_CMDLINE
EOF
fi

# Also update the default zen entry
for f in /boot/loader/entries/mavericks-linux-zen*.conf; do
  [[ -f "$f" ]] || continue
  if grep -q "^options" "$f"; then
    sed -i -E "s/^(options +.*rootflags=[^ ]+ *) .*/\1 $FINAL_CMDLINE/" "$f" || true
  fi
done

# --- 8. Пересборка initramfs и загрузчика ---
echo
echo "=== Regenerating initramfs & Bootloader ==="
mkinitcpio -P
bootctl update

# --- 9. Включение сервисов ---
echo
echo "=== Enabling Services ==="
# Phase 0.3: TLP + zram + bluetooth only. NO thermald/ananicy (REMOVED).
systemctl enable --now bluetooth.service 2>/dev/null || true
systemctl enable --now tlp 2>/dev/null || true
systemctl enable --now systemd-zram-setup@zram0 2>/dev/null || true

# --- 10. Применение темы для текущего пользователя ---
echo
echo "=== Applying Mavericks Theme ==="
CURRENT_USER=$(logname 2>/dev/null || echo "$SUDO_USER")
if [[ -n "$CURRENT_USER" && "$CURRENT_USER" != "root" ]]; then
    USER_HOME=$(eval echo "~$CURRENT_USER")
    sudo -u "$CURRENT_USER" bash -c "
        mkdir -p \"\$USER_HOME/.config/gtk-3.0\"
        cat > \"\$USER_HOME/.config/gtk-3.0/settings.ini\" <<'GTKEOF'
[Settings]
gtk-theme-name=Mavericks
gtk-icon-theme-name=Mavericks
gtk-cursor-theme-name=Mavericks-Cursors
gtk-cursor-theme-size=24
gtk-font-name=San Francisco 11
gtk-enable-animations=1
gtk-enable-event-sounds=1
gtk-enable-input-feedback-sounds=1
gtk-xft-antialias=1
gtk-xft-hinting=1
gtk-xft-hintstyle=hintslight
gtk-xft-rgba=rgb
GTKEOF

        mkdir -p \"\$USER_HOME/.config/plank/dock1\"
        cat > \"\$USER_HOME/.config/plank/dock1/settings\" <<'PLANKEOF'
[PlankDockPreferences]
Theme=Mavericks
ZoomEnabled=true
ZoomPercent=150
IconSize=48
HideMode=0
ShowDockItem=false
PressureReveal=false
PressureRevealTime=0.5
Alignment=0
Position=0
Offset=0
Monitor=-1
IconZoom=true
UrgentHueShift=0.5
PLANKEOF

        # Epiphany Mavericks profile
        /usr/bin/epiphany-mavericks-setup 2>/dev/null || true
    "
fi

# --- 11. Итог ---
echo
echo "=== Setup Complete ==="
echo "Model: $MODEL"
echo "Wi-Fi: $WIFI_DRIVER"
echo "Audio: $AUDIO_DRIVER"
echo "Bluetooth: $BT_DRIVER"
echo "applespi: $SPI_DRIVER"
echo
echo "Log saved to: $LOG_FILE"
echo
echo "REBOOT REQUIRED to apply kernel/initramfs changes."
read -p "Reboot now? (y/N) " -n 1 -r
echo
[[ $REPLY =~ ^[Yy]$ ]] && reboot