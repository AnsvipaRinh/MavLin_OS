#!/usr/bin/env bash

# contrib/discovery-status.sh — Read-only discovery status wrapper for orchestrator
# Provides machine-readable gate result without executing arbitrary code
# Returns clear status: OK|EMPTY|FILE_NOT_FOUND|UNAVAILABLE|AUTH_INVALID|RATE_LIMITED|EXECUTION_ERROR|DISCOVERY_FAILED

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_DIR="${REPO_ROOT}/lab/contrib"
BACKLOG_FILE="${STATE_DIR}/backlog.json"

# Exit codes for status function:
# 0 - OK (with items)
# 1 - UNAVAILABLE (GitHub unavailable)
# 2 - AUTH_INVALID (GitHub auth invalid)
# 3 - RATE_LIMITED (GitHub rate limited)
# 4 - FILE_NOT_FOUND (file missing)
# 5 - EXECUTION_ERROR (discover.sh failed for other reasons)

# Function to print machine-readable status and return status code
# Usage: discovery_status (requires jq)
get_discovery_status() {
    local json_output=""
    
    if [[ ! -f "${BACKLOG_FILE}" ]]; then
        json_output=$(jq -n \
            --arg status "FILE_NOT_FOUND" \
            --arg reason "discovery backlog.json file not found" \
            --arg exit_code "4" \
            --argjson count "0" \
            '{status: $status, reason: $reason, exit_code: ($exit_code | tonumber), total_count: $count}')
        echo "$json_output"
        return 4
    fi
    
    # Read existing backlog.json
    if ! discovery_status=$(jq -r '.discovery_status // "UNKNOWN"' "${BACKLOG_FILE}" 2>/dev/null); then
        json_output=$(jq -n \
            --arg status "EXECUTION_ERROR" \
            --arg reason "failed to parse backlog.json" \
            --arg exit_code "5" \
            --argjson count "0" \
            '{status: $status, reason: $reason, exit_code: ($exit_code | tonumber), total_count: $count}')
        echo "$json_output"
        return 5
    fi
    
    # Extract total_count
    local total_count=0
    if total_count_val=$(jq -r '.total_count // 0' "${BACKLOG_FILE}" 2>/dev/null); then
        total_count=$total_count_val
    fi
    
    case "$discovery_status" in
        "OK")
            if [[ $total_count -gt 0 ]]; then
                json_output=$(jq -n \
                    --arg status "OK" \
                    --arg reason "discovery completed successfully with $total_count items" \
                    --arg exit_code "0" \
                    --argjson count "$total_count" \
                    '{status: $status, reason: $reason, exit_code: ($exit_code | tonumber), total_count: $count}')
                echo "$json_output"
                return 0
            else
                json_output=$(jq -n \
                    --arg status "EMPTY" \
                    --arg reason "discovery completed successfully, no actionable items" \
                    --arg exit_code "1" \
                    --argjson count "$total_count" \
                    '{status: $status, reason: $reason, exit_code: ($exit_code | tonumber), total_count: $count}')
                echo "$json_output"
                return 1
            fi
            ;;
        "UNAVAILABLE")
            json_output=$(jq -n \
                --arg status "UNAVAILABLE" \
                --arg reason "GitHub discovery failed: unavailable" \
                --arg exit_code "1" \
                --argjson count "$total_count" \
                '{status: $status, reason: $reason, exit_code: ($exit_code | tonumber), total_count: $count}')
            echo "$json_output"
            return 1
            ;;
        "AUTH_INVALID")
            json_output=$(jq -n \
                --arg status "AUTH_INVALID" \
                --arg reason "GitHub discovery failed: authentication invalid" \
                --arg exit_code "2" \
                --argjson count "$total_count" \
                '{status: $status, reason: $reason, exit_code: ($exit_code | tonumber), total_count: $count}')
            echo "$json_output"
            return 2
            ;;
        "RATE_LIMITED")
            json_output=$(jq -n \
                --arg status "RATE_LIMITED" \
                --arg reason "GitHub discovery failed: rate limited" \
                --arg exit_code "3" \
                --argjson count "$total_count" \
                '{status: $status, reason: $reason, exit_code: ($exit_code | tonumber), total_count: $count}')
            echo "$json_output"
            return 3
            ;;
        *)
            # DISCOVERY_FAILED for unknown/disconnected status
            json_output=$(jq -n \
                --arg status "DISCOVERY_FAILED" \
                --arg reason "discovery completed with status: ${discovery_status}"' \
                --arg exit_code "5" \
                --argjson count "$total_count" \
                '{status: $status, reason: $reason, exit_code: ($exit_code | tonumber), total_count: $count}')
            echo "$json_output"
            return 5
            ;;
    esac
}

# Main execution: output status JSON and exit with status code
if command -v jq >/dev/null 2>&1; then
    get_discovery_status
    # Output to stdout for easy consumption
    exit ${?}
else
    echo "ERROR: jq is required for contrib/discovery-status.sh" >&2
    exit 127
fi
