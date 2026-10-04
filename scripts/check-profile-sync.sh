#!/usr/bin/env bash
# check-profile-sync.sh — Verify profile + firstboot runtime contract
# Run in CI / pre-commit to catch drift between source configs, airootfs,
# and scripts/install mirrors.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AIROOTFS="$REPO_ROOT/archiso-profile/releng/airootfs"
INSTALL_SRC="$REPO_ROOT/scripts/install"
ERRORS=0

check_file() {
    local src="$1"
    local dst="$2"
    local desc="$3"
    if [[ ! -f "$src" ]]; then
        echo "ERROR: source missing: $src ($desc)"
        ((ERRORS++)) || true
        return
    fi
    if [[ ! -f "$dst" ]]; then
        echo "ERROR: destination missing: $dst ($desc)"
        ((ERRORS++)) || true
        return
    fi
    if ! cmp -s "$src" "$dst"; then
        echo "ERROR: drift detected: $src != $dst ($desc)"
        echo "  diff:"
        diff -u "$src" "$dst" | sed 's/^/    /' || true
        ((ERRORS++)) || true
    fi
}

require_file() {
    local path="$1"
    local desc="$2"
    if [[ ! -f "$path" ]]; then
        echo "ERROR: missing: $path ($desc)"
        ((ERRORS++)) || true
    fi
}

log() { echo "[check-profile-sync] $*"; }

log "Checking profile + firstboot runtime contract..."

# --- Fragments: configs/profiles/fragments → airootfs store ---
check_file "$REPO_ROOT/configs/profiles/fragments/99-mavericks-s3x.conf" \
    "$AIROOTFS/usr/local/share/mavericks/profiles/fragments/99-mavericks-s3x.conf" \
    "S3X fragment"

check_file "$REPO_ROOT/configs/profiles/fragments/99-mavericks-display.conf" \
    "$AIROOTFS/usr/local/share/mavericks/profiles/fragments/99-mavericks-display.conf" \
    "display fragment"

# --- Generic profile baseline (source of truth in configs/) ---
check_file "$REPO_ROOT/configs/profiles/generic/baseline.conf" \
    "$AIROOTFS/usr/local/share/mavericks/profiles/generic/baseline.conf" \
    "generic baseline.conf"

# Generic runtime configs that land outside the share store
check_file "$REPO_ROOT/configs/profiles/generic/99-mavericks-network.conf" \
    "$AIROOTFS/etc/NetworkManager/conf.d/99-mavericks.conf" \
    "generic network (connectivity)"

check_file "$REPO_ROOT/configs/profiles/generic/99-mavericks-tlp.conf" \
    "$AIROOTFS/etc/tlp.d/99-mavericks.conf" \
    "generic TLP"

check_file "$REPO_ROOT/configs/profiles/generic/99-mavericks-zram.conf" \
    "$AIROOTFS/etc/systemd/zram-generator.conf.d/99-mavericks.conf" \
    "generic zram"

check_file "$REPO_ROOT/configs/profiles/generic/99-mavericks-modprobe.conf" \
    "$AIROOTFS/etc/modprobe.d/99-mavericks.conf" \
    "generic modprobe"

# --- MacBook manifest ---
check_file "$REPO_ROOT/configs/profiles/macbook10,1/manifest.conf" \
    "$AIROOTFS/usr/local/share/mavericks/profiles/macbook10,1/manifest.conf" \
    "macbook10,1 manifest"

# MacBook-specific airootfs fragments that must exist (profile-gated at runtime)
require_file "$AIROOTFS/etc/NetworkManager/conf.d/99-mavericks-wifi-backend.conf" "MacBook Wi-Fi backend"
require_file "$AIROOTFS/etc/tlp.d/99-mavericks-power.conf" "MacBook TLP power"
require_file "$AIROOTFS/etc/mkinitcpio.conf.d/99-mavericks-spi.conf" "MacBook SPI"
require_file "$AIROOTFS/usr/local/bin/mavericks/extract-brcmfmac-nvram.sh" "NVRAM script"

# --- Firstboot + selector: airootfs is runtime truth; scripts/install must match ---
require_file "$AIROOTFS/usr/local/bin/mavericks/mavericks-firstboot.sh" "airootfs firstboot"
require_file "$AIROOTFS/usr/local/bin/mavericks/mavericks-profile-select.sh" "airootfs profile-select"
require_file "$INSTALL_SRC/mavericks-firstboot.sh" "scripts/install firstboot"
require_file "$INSTALL_SRC/mavericks-profile-select.sh" "scripts/install profile-select"

check_file "$AIROOTFS/usr/local/bin/mavericks/mavericks-firstboot.sh" \
    "$INSTALL_SRC/mavericks-firstboot.sh" \
    "firstboot airootfs ↔ scripts/install"

check_file "$AIROOTFS/usr/local/bin/mavericks/mavericks-profile-select.sh" \
    "$INSTALL_SRC/mavericks-profile-select.sh" \
    "profile-select airootfs ↔ scripts/install"

# --- Runtime contract assertions on firstboot ---
FB="$AIROOTFS/usr/local/bin/mavericks/mavericks-firstboot.sh"
if [[ -f "$FB" ]]; then
    if ! grep -q 'source.*PROFILE_CONF' "$FB"; then
        echo "ERROR: firstboot does not source PROFILE_CONF"
        ((ERRORS++)) || true
    fi
    if ! grep -q 'macbook10,1' "$FB"; then
        echo "ERROR: firstboot missing explicit macbook10,1 equality gate"
        ((ERRORS++)) || true
    fi
    # Must not hard-depend on a repo checkout path for normal operation
    if grep -qE 'REPO_DIR=|Clone the repo' "$FB"; then
        echo "ERROR: firstboot still has REPO_DIR / clone-required hard dependency"
        ((ERRORS++)) || true
    fi
    if ! grep -q 'firstboot-complete' "$FB"; then
        echo "ERROR: firstboot missing completion marker handling"
        ((ERRORS++)) || true
    fi
    if ! grep -q '/usr/local/share/mavericks/profiles' "$FB"; then
        echo "ERROR: firstboot does not use installed profile store path"
        ((ERRORS++)) || true
    fi
fi

# --- Runtime contract assertions on selector ---
PS="$AIROOTFS/usr/local/bin/mavericks/mavericks-profile-select.sh"
if [[ -f "$PS" ]]; then
    if grep -qE 'REPO_ROOT|configs/profiles' "$PS"; then
        echo "ERROR: profile-select still depends on source-tree configs/profiles path"
        ((ERRORS++)) || true
    fi
    if ! grep -q 'generic' "$PS"; then
        echo "ERROR: profile-select missing generic fallback"
        ((ERRORS++)) || true
    fi
    if ! grep -q '/usr/local/share/mavericks/profiles' "$PS"; then
        echo "ERROR: profile-select missing installed PROFILE_STORE path"
        ((ERRORS++)) || true
    fi
fi

# --- Systemd oneshot must be shipped and enabled ---
require_file "$AIROOTFS/etc/systemd/system/mavericks-firstboot.service" "firstboot unit"
require_file "$AIROOTFS/etc/systemd/system/multi-user.target.wants/mavericks-firstboot.service" \
    "firstboot enabled in multi-user.target.wants"

if [[ -f "$AIROOTFS/etc/systemd/system/mavericks-firstboot.service" ]]; then
    if ! grep -q 'mavericks-firstboot.sh' "$AIROOTFS/etc/systemd/system/mavericks-firstboot.service"; then
        echo "ERROR: firstboot unit does not ExecStart the firstboot script"
        ((ERRORS++)) || true
    fi
    if ! grep -q 'Type=oneshot' "$AIROOTFS/etc/systemd/system/mavericks-firstboot.service"; then
        echo "ERROR: firstboot unit is not Type=oneshot"
        ((ERRORS++)) || true
    fi
fi

# --- Graceful degradation: generic baseline must not carry MacBook params ---
if [[ -f "$REPO_ROOT/configs/profiles/generic/baseline.conf" ]]; then
    if grep -qE 'pcie_port_pm=off|i915\.enable_psr=0' "$REPO_ROOT/configs/profiles/generic/baseline.conf"; then
        echo "ERROR: generic baseline contains MacBook-specific kernel params"
        ((ERRORS++)) || true
    fi
fi

# --- MacBook manifest references ---
if [[ -f "$REPO_ROOT/configs/profiles/macbook10,1/manifest.conf" ]]; then
    for ref in 99-mavericks-s3x.conf 99-mavericks-display.conf \
               99-mavericks-wifi-backend.conf 99-mavericks-power.conf \
               99-mavericks-spi.conf extract-brcmfmac-nvram.sh; do
        if ! grep -q "$ref" "$REPO_ROOT/configs/profiles/macbook10,1/manifest.conf"; then
            echo "ERROR: MacBook manifest missing reference: $ref"
            ((ERRORS++)) || true
        fi
    done
fi

if (( ERRORS > 0 )); then
    echo
    log "FAIL: $ERRORS sync/contract error(s) detected"
    exit 1
else
    log "OK: profile + firstboot runtime contract satisfied"
    exit 0
fi
