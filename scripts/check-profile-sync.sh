#!/usr/bin/env bash
# check-profile-sync.sh — Verify airootfs mirrors configs/profiles/
# Run in CI / pre-commit to catch drift between source configs and installed airootfs
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AIROOTFS="$REPO_ROOT/archiso-profile/releng/airootfs"
ERRORS=0

check_file() {
    local src="$1"
    local dst="$2"
    local desc="$3"
    if [[ ! -f "$src" ]]; then
        echo "ERROR: source missing: $src ($desc)"
        ((ERRORS++))
        return
    fi
    if [[ ! -f "$dst" ]]; then
        echo "ERROR: destination missing: $dst ($desc)"
        ((ERRORS++))
        return
    fi
    if ! cmp -s "$src" "$dst"; then
        echo "ERROR: drift detected: $src != $dst ($desc)"
        echo "  diff:"
        diff -u "$src" "$dst" | sed 's/^/    /' || true
        ((ERRORS++))
    fi
}

log() { echo "[check-sync] $*"; }

log "Checking profile sync: configs/profiles/ → airootfs..."

# generic profile files
check_file "$REPO_ROOT/configs/profiles/generic/baseline.conf" \
    "$AIROOTFS/usr/local/share/mavericks/profiles/generic/baseline.conf" \
    "generic baseline.conf"

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

# macbook10,1 profile manifest
check_file "$REPO_ROOT/configs/profiles/macbook10,1/manifest.conf" \
    "$AIROOTFS/usr/local/share/mavericks/profiles/macbook10,1/manifest.conf" \
    "macbook10,1 manifest"

# MacBook-specific fragments (source in configs/profiles/fragments/)
check_file "$REPO_ROOT/configs/profiles/fragments/99-mavericks-s3x.conf" \
    "$AIROOTFS/usr/local/share/mavericks/profiles/fragments/99-mavericks-s3x.conf" \
    "S3X fragment"

check_file "$REPO_ROOT/configs/profiles/fragments/99-mavericks-display.conf" \
    "$AIROOTFS/usr/local/share/mavericks/profiles/fragments/99-mavericks-display.conf" \
    "display fragment"

check_file "$REPO_ROOT/scripts/install/mavericks-profile-select.sh" \
    "$AIROOTFS/usr/local/bin/mavericks/mavericks-profile-select.sh" \
    "installed profile selector"

[[ -f "$AIROOTFS/etc/systemd/system/mavericks-firstboot.service" ]] || {
    echo "ERROR: firstboot systemd unit missing in airootfs"
    ((ERRORS++))
}
[[ -L "$AIROOTFS/etc/systemd/system/multi-user.target.wants/mavericks-firstboot.service" ]] || {
    echo "ERROR: firstboot systemd unit is not enabled in airootfs"
    ((ERRORS++))
}

# MacBook-specific airootfs files (not mirrored from configs/profiles/, but must exist)
[[ -f "$AIROOTFS/etc/NetworkManager/conf.d/99-mavericks-wifi-backend.conf" ]] || {
    echo "ERROR: MacBook Wi-Fi backend fragment missing in airootfs"
    ((ERRORS++))
}
[[ -f "$AIROOTFS/etc/tlp.d/99-mavericks-power.conf" ]] || {
    echo "ERROR: MacBook TLP power fragment missing in airootfs"
    ((ERRORS++))
}
[[ -f "$AIROOTFS/etc/mkinitcpio.conf.d/99-mavericks-spi.conf" ]] || {
    echo "ERROR: MacBook SPI fragment missing in airootfs"
    ((ERRORS++))
}
[[ -f "$AIROOTFS/usr/local/bin/mavericks/extract-brcmfmac-nvram.sh" ]] || {
    echo "ERROR: NVRAM script missing in airootfs"
    ((ERRORS++))
}
[[ -f "$AIROOTFS/usr/local/bin/mavericks/mavericks-profile-select.sh" ]] || {
    echo "ERROR: profile selector missing in airootfs"
    ((ERRORS++))
}
[[ -f "$AIROOTFS/usr/local/bin/mavericks/mavericks-firstboot.sh" ]] || {
    echo "ERROR: firstboot script missing in airootfs"
    ((ERRORS++))
}

# Legacy hardware-selection entry point must not carry a second driver-selection tree.
if grep -q 'broadcom-wl-dkms\|macbook12-bluetooth-driver\|epiphany-mavericks-theme' "$REPO_ROOT/scripts/apply-hardware-selection.sh"; then
    echo "ERROR: legacy hardware selector still contains obsolete package branches"
    ((ERRORS++))
fi

# firstboot must use installed runtime assets, not a source checkout
if grep -q 'REPO_DIR.*archiso-profile\|Clone the repo\|repo checkout not found' "$AIROOTFS/usr/local/bin/mavericks/mavericks-firstboot.sh"; then
    echo "ERROR: firstboot still depends on a source-tree checkout"
    ((ERRORS++))
fi
if ! grep -q 'PROFILE_STORE=.*usr/local/share/mavericks/profiles' "$AIROOTFS/usr/local/bin/mavericks/mavericks-firstboot.sh"; then
    echo "ERROR: firstboot does not use installed profile store"
    ((ERRORS++))
fi

# profile selector script must exist
[[ -f "$REPO_ROOT/scripts/install/mavericks-profile-select.sh" ]] || {
    echo "ERROR: profile selector script missing"
    ((ERRORS++))
}

# profile selector must be executable
[[ -x "$REPO_ROOT/scripts/install/mavericks-profile-select.sh" ]] || {
    echo "ERROR: profile selector script not executable"
    ((ERRORS++))
}

# Verify graceful degradation: generic profile has NO MacBook-specific fragments
if [[ -f "$REPO_ROOT/configs/profiles/generic/baseline.conf" ]]; then
    if grep -q "pcie_port_pm=off\|i915.enable_psr=0" "$REPO_ROOT/configs/profiles/generic/baseline.conf"; then
        echo "ERROR: generic baseline contains MacBook-specific kernel params"
        ((ERRORS++))
    fi
fi

# Verify MacBook profile manifest references correct fragments
if [[ -f "$REPO_ROOT/configs/profiles/macbook10,1/manifest.conf" ]]; then
    if ! grep -q "99-mavericks-s3x.conf" "$REPO_ROOT/configs/profiles/macbook10,1/manifest.conf"; then
        echo "ERROR: MacBook manifest missing S3X fragment reference"
        ((ERRORS++))
    fi
    if ! grep -q "99-mavericks-display.conf" "$REPO_ROOT/configs/profiles/macbook10,1/manifest.conf"; then
        echo "ERROR: MacBook manifest missing display fragment reference"
        ((ERRORS++))
    fi
    if ! grep -q "99-mavericks-wifi-backend.conf" "$REPO_ROOT/configs/profiles/macbook10,1/manifest.conf"; then
        echo "ERROR: MacBook manifest missing Wi-Fi backend reference"
        ((ERRORS++))
    fi
    if ! grep -q "99-mavericks-power.conf" "$REPO_ROOT/configs/profiles/macbook10,1/manifest.conf"; then
        echo "ERROR: MacBook manifest missing TLP power reference"
        ((ERRORS++))
    fi
    if ! grep -q "99-mavericks-spi.conf" "$REPO_ROOT/configs/profiles/macbook10,1/manifest.conf"; then
        echo "ERROR: MacBook manifest missing SPI reference"
        ((ERRORS++))
    fi
    if ! grep -q "extract-brcmfmac-nvram.sh" "$REPO_ROOT/configs/profiles/macbook10,1/manifest.conf"; then
        echo "ERROR: MacBook manifest missing NVRAM script reference"
        ((ERRORS++))
    fi
fi

if (( ERRORS > 0 )); then
    echo
    log "FAIL: $ERRORS sync error(s) detected"
    exit 1
else
    log "OK: all profile files in sync"
    exit 0
fi