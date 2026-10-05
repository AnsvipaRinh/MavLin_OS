#!/usr/bin/env bash
# mavericks-firstboot.sh — one-shot post-install setup (as root)
# Self-contained: does NOT require a Git checkout on the target machine.
# Idempotent via /etc/mavericks/firstboot-complete. Reboot after first run.
set -euo pipefail

log() { echo "[firstboot] $*"; }

PROFILE_SELECTOR="/usr/local/bin/mavericks/mavericks-profile-select.sh"
PROFILE_STORE="/usr/local/share/mavericks/profiles"
PROFILE_CONF="/etc/mavericks/profile.conf"
COMPLETE_MARKER="/etc/mavericks/firstboot-complete"

if [[ -f "$COMPLETE_MARKER" ]]; then
  log "firstboot already completed ($COMPLETE_MARKER); nothing to do."
  exit 0
fi

if [[ ! -x "$PROFILE_SELECTOR" ]]; then
  echo "[firstboot] ERROR: installed profile selector missing: $PROFILE_SELECTOR" >&2
  exit 1
fi
if [[ ! -d "$PROFILE_STORE" ]]; then
  echo "[firstboot] ERROR: installed profile store missing: $PROFILE_STORE" >&2
  exit 1
fi

# Select profile once (unknown hardware → generic).
if [[ ! -f "$PROFILE_CONF" ]]; then
  log "No profile config yet — running selector"
  "$PROFILE_SELECTOR"
fi

MAVERICKS_PROFILE=""
if [[ -f "$PROFILE_CONF" ]]; then
  # shellcheck disable=SC1090
  source "$PROFILE_CONF"
  log "profile: ${MAVERICKS_PROFILE:-unknown}"
else
  log "WARNING: profile.conf still absent after selector — treating as generic"
  MAVERICKS_PROFILE="generic"
fi

# Explicit equality only: absence must never enable MacBook fragments.
macbook_profile() {
  [[ "${MAVERICKS_PROFILE:-}" == "macbook10,1" ]]
}

log "1/8 hostname/locale/time"
# Preserve a hostname selected by the installer or administrator. Only use the
# project default when the installed system has no static hostname yet.
CURRENT_HOSTNAME="$(hostnamectl --static 2>/dev/null || true)"
if [[ -n "$CURRENT_HOSTNAME" ]]; then
  log "preserving existing static hostname: $CURRENT_HOSTNAME"
else
  hostnamectl set-hostname mavericks-linux 2>/dev/null || echo mavericks-linux > /etc/hostname
  log "no static hostname configured — using default: mavericks-linux"
fi
ln -sf /usr/share/zoneinfo/Europe/Berlin /etc/localtime 2>/dev/null || true
hwclock --systohc 2>/dev/null || true

log "2/8 bootloader entries = baseline + profile fragments"
BASE_CMDLINE="quiet loglevel=3"
FRAGMENT_DIR="$PROFILE_STORE/fragments"
MACBOOK_FRAGMENTS=()
if macbook_profile; then
  [[ -f "$FRAGMENT_DIR/99-mavericks-s3x.conf" ]] && \
    MACBOOK_FRAGMENTS+=("$(grep -v '^#' "$FRAGMENT_DIR/99-mavericks-s3x.conf" | tr -d '\n')")
  [[ -f "$FRAGMENT_DIR/99-mavericks-display.conf" ]] && \
    MACBOOK_FRAGMENTS+=("$(grep -v '^#' "$FRAGMENT_DIR/99-mavericks-display.conf" | tr -d '\n')")
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
grep -H "^options" /boot/loader/entries/*.conf 2>/dev/null || true

log "3/8 TLP + power fragment policy"
systemctl enable tlp.service 2>/dev/null || true
if ! macbook_profile; then
  rm -f /etc/tlp.d/99-mavericks-power.conf
fi
rm -f /etc/tlp.d/10-experiment.conf

log "4/8 zram"
systemctl enable systemd-zram-setup@zram0.service 2>/dev/null || true
rm -f /etc/sysctl.d/99-mavericks.conf

log "5/8 network: NetworkManager owns Wi-Fi"
if ! macbook_profile; then
  rm -f /etc/NetworkManager/conf.d/99-mavericks-wifi-backend.conf
fi
systemctl disable --now iwd.service 2>/dev/null || true
systemctl disable --now systemd-networkd.service systemd-networkd-wait-online.service 2>/dev/null || true
systemctl enable NetworkManager.service 2>/dev/null || true
systemctl enable systemd-resolved.service 2>/dev/null || true
systemctl mask ModemManager.service 2>/dev/null || true
systemctl disable sshd.service reflector.service 2>/dev/null || true
passwd -l root 2>/dev/null || true

log "6/8 snapshot (best-effort) + fstrim"
if command -v btrfs >/dev/null 2>&1 && mountpoint -q "/@snapshots" 2>/dev/null; then
  /usr/local/bin/mavericks/mv-snapshot-take "firstboot-$(date +%Y%m%d%H%M%S)" "Firstboot pre-change" 2>/dev/null || true
else
  log "not on btrfs /@snapshots — skip snapshot"
fi
systemctl enable fstrim.timer 2>/dev/null || true

# Seed GTK/Thunar bookmarks for the primary non-root user (Finder sidebar).
seed_bookmarks() {
  local user="$1"
  local home
  home="$(getent passwd "$user" | cut -d: -f6)"
  [[ -n "$home" && -d "$home" ]] || return 0
  local template="/etc/skel/.gtk-bookmarks.template"
  local out_gtk="$home/.gtk-bookmarks"
  local out_gtk3="$home/.config/gtk-3.0/bookmarks"
  local content
  if [[ -f "$template" ]]; then
    content="$(sed "s|@HOME@|$home|g; /^#/d; /^$/d" "$template")"
  else
    content="file://$home/Desktop Desktop
file://$home/Documents Documents
file://$home/Downloads Downloads
file://$home/Music Music
file://$home/Pictures Pictures
file://$home/Movies Movies"
  fi
  # Do not overwrite bookmarks that the user or installer already created.
  if [[ ! -e "$out_gtk" ]]; then
    printf '%s\\n' "$content" > "$out_gtk"
    chown "$user:$user" "$out_gtk" 2>/dev/null || true
  else
    log "preserving existing $out_gtk"
  fi
  mkdir -p "$(dirname "$out_gtk3")"
  if [[ ! -e "$out_gtk3" ]]; then
    printf '%s\\n' "$content" > "$out_gtk3"
    chown "$user:$user" "$out_gtk3" 2>/dev/null || true
  else
    log "preserving existing $out_gtk3"
  fi
  # Create the standard directories if absent, but never recursively chown
  # existing user data during firstboot.
  mkdir -p "$home/Movies" "$home/Desktop" "$home/Documents" "$home/Downloads" \
           "$home/Music" "$home/Pictures"
  log "seeded/preserved GTK bookmarks for $user"
}

log "7/8 session services + index"
systemctl enable lightdm.service 2>/dev/null || true
systemctl enable bluetooth.service 2>/dev/null || true
systemctl enable plocate-updatedb.timer 2>/dev/null || true
rm -f /etc/systemd/journald.conf.d/volatile-storage.conf 2>/dev/null || true

TARGET_USER="${SUDO_USER:-$(logname 2>/dev/null || true)}"
if [[ -n "$TARGET_USER" && "$TARGET_USER" != "root" ]]; then
  sudo -u "$TARGET_USER" systemctl --user enable mv-reminders-check.timer 2>/dev/null || true
  sudo -u "$TARGET_USER" systemctl --user enable mv-calendar-check.timer 2>/dev/null || true
  seed_bookmarks "$TARGET_USER"
fi

log "8/8 MacBook NVRAM (profile-gated)"
if macbook_profile && [[ -x /usr/local/bin/mavericks/extract-brcmfmac-nvram.sh ]]; then
  /usr/local/bin/mavericks/extract-brcmfmac-nvram.sh || true
fi

mkdir -p "$(dirname "$COMPLETE_MARKER")"
install -Dm644 /dev/null "$COMPLETE_MARKER"
log "Done. Marker: $COMPLETE_MARKER. REBOOT recommended."
