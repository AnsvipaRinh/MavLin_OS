#!/usr/bin/env bash
# mavericks-rollback.sh — restore system from latest pre-change snapshot
# Usage: sudo ./mavericks-rollback.sh <experiment-id> [label-prefix]
#   experiment-id — experiment to rollback (E1..E12)
#   label-prefix — optional prefix for snapshot label (default: "exp-<id>")
# Description: restore @, @home, @var_log from latest pre-change snapshot matching the prefix
# Note: This is a single rollback procedure matching our layout (no new daemon)

set -euo pipefail

# Configuration
SNAPSHOT_MOUNT="/@snapshots"
BACKUP_DIR="/var/lib/mavericks-experiments"
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

# Logging function
log() {
    echo "[rollback] $*"
}

# Check if we're on btrfs with snapshots
check_btrfs() {
    if ! command -v btrfs >/dev/null 2>&1; then
        log "ERROR: btrfs command not available - cannot rollback"
        return 1
    fi
    if ! mountpoint -q "$SNAPSHOT_MOUNT"; then
        log "ERROR: $SNAPSHOT_MOUNT not mounted - cannot rollback"
        return 1
    fi
    return 0
}

# Find latest snapshot matching the pattern
find_latest_snapshot() {
    local prefix="$1"
    local snapshots_dir="$(basename "$SNAPSHOT_MOUNT")"
    
    # Find all subdirectories in snapshots matching the prefix pattern
    local matching_snapshots=($(find "$SNAPSHOT_MOUNT" -maxdepth 1 -type d -name "${prefix}-*" 2>/dev/null | sort -r))
    
    if [[ ${#matching_snapshots[@]} -eq 0 ]]; then
        log "ERROR: No snapshots found with prefix '$prefix' in $SNAPSHOT_MOUNT"
        return 1
    fi
    
    local latest_snapshot="${matching_snapshots[0]}"
    log "Found latest snapshot: $latest_snapshot"
    echo "$latest_snapshot"
}

# Restore files from snapshot
restore_from_snapshot() {
    local snapshot_path="$1"
    local target_dir="$2"
    
    local source_path="${snapshot_path}${target_dir}"
    local target_path="${target_dir#/}"
    
    log "Restoring ${target_dir} from ${snapshot_path}"
    
    if [[ ! -d "$source_path" ]]; then
        log "WARN: Source ${source_path} does not exist in snapshot"
        return 1
    fi
    
    # Restore by copying from snapshot (overwrites existing files)
    # Do NOT rm -rf system directories - use cp -a to overwrite
    cp -a "$source_path/." "$target_path/" 2>/dev/null
    
    if [[ $? -eq 0 ]]; then
        log "Successfully restored ${target_path}"
        return 0
    else
        log "ERROR: Failed to restore ${target_path}"
        return 1
    fi
}

# Main rollback procedure
main() {
    if [[ $# -lt 1 ]]; then
        echo "Usage: $0 <experiment-id> [label-prefix]"
        echo "  experiment-id — experiment to rollback (E1..E12)"
        echo "  label-prefix — optional prefix for snapshot label (default: \"exp-<id>\")"
        exit 1
    fi
    
    local experiment_id="$1"
    local label_prefix="${2:-exp-$experiment_id}"
    
    log "Starting rollback for experiment: $experiment_id"
    log "Looking for snapshots with prefix: $label_prefix"
    
    # Check if we're on btrfs
    if ! check_btrfs; then
        log "Rolling back without btrfs snapshots - using backup files from $BACKUP_DIR"
        # Fallback: restore from experiment backup files
        for file in "$BACKUP_DIR"/*.bak; do
            local target="$(basename "$file" .bak)"
            log "Restoring $target from backup"
            cp -a "$file" "/$target" 2>/dev/null || true
        done
        return
    fi
    
    # Find latest snapshot
    local snapshot_path
    if ! snapshot_path=$(find_latest_snapshot "$label_prefix"); then
        log "ERROR: Could not find snapshot for rollback"
        exit 1
    fi
    
    # Restore from snapshot
    local restore_success=0
    
    # Restore root filesystem
    if restore_from_snapshot "$snapshot_path" "/"; then
        ((restore_success++))
    fi
    
    # Restore home directory (common case)
    if restore_from_snapshot "$snapshot_path" "/home"; then
        ((restore_success++))
    fi
    
    # Restore var_log (if it exists)
    if restore_from_snapshot "$snapshot_path" "/var/log"; then
        ((restore_success++))
    fi
    
    # Log completion
    if [[ $restore_success -gt 0 ]]; then
        log "Rollback completed successfully ($restore_success directories restored)"
        log "For complete recovery, consider restoring bootloader from baseline:"
        log "  $REPO_DIR/configs/profiles/baseline.conf"
    else
        log "WARN: No directories were successfully restored"
    fi
}

main "$@"
