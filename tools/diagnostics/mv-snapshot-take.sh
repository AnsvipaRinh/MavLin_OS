#!/usr/bin/env bash
# mv-snapshot-take — create pre-change btrfs snapshot with timestamp label
# Usage: mv-snapshot-take <label> [description]
#   label — short human-readable name (must be non-empty, alphanumeric+hyphens)
#   description — optional, logged to snapshot record file
# Returns: 0 on success, 1 on failure
# Safety: NEVER fails the wrapped operation if snapshotting unavailable (logs + continues)

# Prunes old snapshots to keep last N per label
# N = 5 (configurable via SNAPSHOT_KEEP_COUNT environment)
# Also keeps latest 10 snapshots overall
# Clean stop: global error count, no exit on failure

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BACKUP_DIR="/@snapshots"
SNAPSHOT_LOG="${BACKUP_DIR}/snapshots.log"
SNAPSHOT_INDEX="${BACKUP_DIR}/index.json"
MAX_SNAPSHOT_HISTORY=10

# Safety: track errors but never exit with failure
eval_error=0

log() {
    echo "[snapshot] $*"
    echo "[snapshot] $*" >> "${SNAPSHOT_LOG}"
}

# Ensure btrfs snapshots directory exists
ensure_snapshot_dir() {
    if ! command -v btrfs >/dev/null 2>&1; then
        log "ERROR: btrfs command not available - no btrfs filesystem to snapshot"
        eval_error=1
        return 1
    fi
    if ! mountpoint -q "${BACKUP_DIR}"; then
        log "ERROR: ${BACKUP_DIR} not mounted - cannot create snapshots"
        eval_error=1
        return 1
    fi
    log "Snapshot directory ${BACKUP_DIR} is available"
    return 0
}

# Validate label: alphanumeric + hyphens only, non-empty, reasonable length
validate_label() {
    local label="$1"
    if [[ -z "$label" ]]; then
        log "ERROR: snapshot label cannot be empty"
        return 1
    fi
    if [[ ${#label} -gt 50 ]]; then
        log "ERROR: snapshot label too long (max 50 chars)"
        return 1
    fi
    if [[ ! "$label" =~ ^[a-zA-Z0-9\-]+$ ]]; then
        log "ERROR: snapshot label must be alphanumeric + hyphens only: '$label'"
        return 1
    fi
    return 0
}

# Create timestamped snapshot directory name
timestamped_dir() {
    local label="$1"
    local timestamp="$(date +%Y%m%dT%H%M%S)"
    echo "@snapshots/${label}-${timestamp}"
}

# Take btrfs snapshot
snapshot_create() {
    local source="${BACKUP_DIR}/.."
    local target="$(timestamped_dir "$1")"
    
    log "Creating btrfs snapshot: ${target} (source: ${source})"
    
    if ! btrfs subvolume snapshot -r "$source" "$target"; then
        log "ERROR: failed to create btrfs snapshot at ${target}"
        eval_error=1
        return 1
    fi
    echo "$target"
}

# Record snapshot in index
record_snapshot() {
    local label="$1"
    local path="$2"
    local desc="$3"
    
    log "Recording snapshot: label=${label}, path=${path}, desc=${desc}"
    
    if ! ensure_snapshot_dir; then
        return 1
    fi
    
    local timestamp="$(date -Iseconds)"
    local record="{\"label\": \"$label\", \"path\": \"$path\", \"timestamp\": \"$timestamp\", \"description\": \"$desc\", \"size\": $(du -s "$path" | cut -f1)}"
    
    # Append to JSON array in index file
    if [[ ! -f "${SNAPSHOT_INDEX}" ]]; then
        echo "[${record}]" > "${SNAPSHOT_INDEX}"
    else
        # Remove closing bracket, append new record, restore closing bracket
        sed -i '${s/$/,/}' "${SNAPSHOT_INDEX}"
        echo "${record}]" >> "${SNAPSHOT_INDEX}"
        # Truncate intermediate brackets if needed
        sed -i 's/\[{[^]]*}/{&/' "${SNAPSHOT_INDEX}" 2>/dev/null || true
    fi
}

# Prune old snapshots: keep last N per label, overall last M
prune_snapshots() {
    log "Pruning old snapshots..."
    
    if ! ensure_snapshot_dir; then
        return
    fi
    
    local keep_per_label="${SNAPSHOT_KEEP_COUNT:-5}"
    local keep_overall="${MAX_SNAPSHOT_HISTORY}"
    
    if [[ ! -f "${SNAPSHOT_INDEX}" ]]; then
        log "No snapshot index found, skipping prune"
        return
    fi
    
    # Create temporary index file for sorting
    local tmp_index="${SNAPSHOT_INDEX}.tmp"
    
    # Parse JSON entries using grep+sed (simple approach, JSON format is deterministic)
    local current_timestamp="$(date +%s)"
    
    # Extract all snapshot entries with paths
    while read -r line; do
        echo "$line"
    done < <(grep -o '{"label": "[^"]*", "path": "[^"]*"' "${SNAPSHOT_INDEX}" 2>/dev/null || echo "") > "${tmp_index}"
    
    # Count entries per label
    local label_counts=""
    local -A label_entries
    
    for entry in $(cat "${tmp_index}"); do
        local label="$(echo "$entry" | grep -o '"label": "[^"]*"' | cut -d'"' -f4)"
        local path="$(echo "$entry" | grep -o '"path": "[^"]*"' | cut -d'"' -f4)"
        
        label_entries["$label"]+="$path "
    done
    
    # Delete old snapshots per label
    for label in "${!label_entries[@]}"; do
        local entries="${label_entries[$label]}"
        local count=0
        
        for entry in $entries; do
            ((count++))
            if (( count > keep_per_label )); then
                log "Pruning old snapshot: ${entry}"
                btrfs subvolume delete "$entry" 2>/dev/null || log "ERROR: failed to delete ${entry}"
                # Also remove from index
                sed -i "s/${entry}//" "${SNAPSHOT_INDEX}"
            fi
        done
    done
    
    # Delete oldest overall snapshots
    if [[ $(wc -l < "${tmp_index}") -gt keep_overall ]]; then
        log "Pruning oldest overall snapshots (keeping last ${keep_overall})"
        local delete_count=$(($(wc -l < "${tmp_index}") - keep_overall))
        local deleted=0
        
        for entry in $(cat "${tmp_index}"); do
            if (( deleted < delete_count )); then
                local path="$(echo "$entry" | grep -o '"path": "[^"]*"' | cut -d'"' -f4)"
                log "Pruning oldest snapshot: ${path}"
                btrfs subvolume delete "$path" 2>/dev/null || log "ERROR: failed to delete ${path}"
                ((deleted++))
            fi
        done
    fi
    
    rm -f "${tmp_index}"
    log "Prune completed"
}

# Get current snapshot count
get_snapshot_count() {
    if [[ -f "${SNAPSHOT_INDEX}" ]]; then
        local count=$(grep -o '"path": "[^"]*"' "${SNAPSHOT_INDEX}" | wc -l)
        echo $count
    else
        echo 0
    fi
}

# Main execution
main() {
    if [[ $# -lt 1 || $# -gt 2 ]]; then
        echo "Usage: $0 <label> [description]"
        echo "  label — short name (alphanumeric + hyphens only)"
        echo "  description — optional, logged to snapshot record"
        return 1
    fi
    
    local label="$1"
    local description="${2:-pre-change snapshot for operation}"
    
    log "Starting snapshot creation: label=${label}, desc=${description}"
    
    # Validate label - log error but NEVER fail the wrapped operation
    if ! validate_label "$label"; then
        log "ERROR: invalid label '$label', snapshot skipped but operation continues"
        return 0
    fi
    
    # Create snapshot - log error but NEVER fail the wrapped operation
    local snapshot_path
    if ! snapshot_path=$(snapshot_create "$label" 2>&1); then
        log "ERROR: snapshot creation failed, operation continues without snapshot"
        return 0
    fi
    
    # Record snapshot
    record_snapshot "$label" "$snapshot_path" "$description"
    
    # Prune old snapshots
    prune_snapshots
    
    log "Snapshot created successfully: ${snapshot_path}"
    log "Snapshot history: $(get_snapshot_count) snapshots"
    
    # Exit with error code if any critical errors occurred during setup
    if [[ $eval_error -ne 0 ]]; then
        log "WARN: some snapshot operations had errors but snapshot succeeded"
    fi
    
    return 0
}

main "$@"
