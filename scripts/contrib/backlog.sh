#!/usr/bin/env bash
# backlog.sh — Compute prioritized actionable contribution backlog
# Reads lab/contrib/backlog.json, optionally refines via triage (no patch fetch),
# deduplicates by objective, outputs work queue for Orchestrator.
# Usage: backlog.sh [--refine] [--output <file>]
# Env: MAVERICKS_STATE_DIR to override state directory (default: REPO_ROOT/lab/contrib)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_DIR="${MAVERICKS_STATE_DIR:-${REPO_ROOT}/lab/contrib}"
BACKLOG_FILE="${STATE_DIR}/backlog.json"
WORKQUEUE_FILE="${STATE_DIR}/workqueue.json"

REFINE=false
OUTPUT_FILE="${WORKQUEUE_FILE}"

while [[ $# -gt 0 ]]; do
    case $1 in
        --refine) REFINE=true ;;
        --output) OUTPUT_FILE="$2"; shift ;;
        *) echo "Usage: $0 [--refine] [--output <file>]"; exit 1 ;;
    esac
    shift
done

if [[ ! -f "${BACKLOG_FILE}" ]]; then
    echo "ERROR: backlog.json not found. Run discover.sh first."
    exit 1
fi

DISCOVERY_STATUS=$(jq -r '.discovery_status' "${BACKLOG_FILE}")
if [[ "${DISCOVERY_STATUS}" != "OK" ]]; then
    echo "Discovery status: ${DISCOVERY_STATUS} — no actionable backlog to compute."
    # Pass through the status
    cat > "${OUTPUT_FILE}" <<EOF
{
  "computed_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "source_discovery_status": "${DISCOVERY_STATUS}",
  "work_queue": [],
  "summary": {"total": 0, "by_objective": {}, "by_priority": {}}
}
EOF
    exit 0
fi

# Priority ordering (P0 first, matching AGENTS.md section 10 roadmap)
declare -A PRIORITY=(
    ["OS-UI-COMPONENT"]=10
    ["OS-UX"]=10
    ["OS-INTEGRATION"]=10
    ["OS-BACKEND"]=20
    ["OS-HW"]=30
    ["OS-ARCH"]=30
    ["OS-PERF"]=20
    ["OS-DOCS"]=40
    ["OS-UI-COSMETIC"]=30
    ["OS-GENERIC"]=50
    ["OS-SEC-REVIEW"]=5
    ["OS-SEC-REJECT"]=1
    ["OS-DUP-CHECK"]=1
    ["OS-IRRELEV"]=0
)

# Hardware scope filtering (AGENTS.md section 7: core + hardware profile separation)
# Contributions can be: core (generic) or profile-specific
# We tag each work item with scope_hint for routing
scope_hint() {
    local classification="$1"
    local title="$2"
    local labels="$3"
    local text="${title} ${labels}"
    text=$(echo "${text}" | tr '[:upper:]' '[:lower:]')
    if echo "${text}" | grep -qE '(macbook|apple|spi|i2c|gpio|acpi|bcm43602|cirrus|nvme|s3x|applespi|trackpad|keyboard|wifi|audio|bluetooth|brightness|thermal|fan|hardware-profile)'; then
        echo "hardware-profile"
    else
        echo "core"
    fi
}

# Read backlog items
PR_ITEMS=$(jq -c '.prs[]' "${BACKLOG_FILE}")
ISSUE_ITEMS=$(jq -c '.issues[]' "${BACKLOG_FILE}")

WORK_ITEMS=()
COUNTER=0

# Process PRs
while IFS= read -r item; do
    [[ -z "${item}" ]] && continue
    COUNTER=$((COUNTER + 1))
    NUMBER=$(echo "${item}" | jq -r '.number')
    TITLE=$(echo "${item}" | jq -r '.title')
    LABELS=$(echo "${item}" | jq -r '.labels')
    HEAD_SHA=$(echo "${item}" | jq -r '.head_sha')
    UPDATED_AT=$(echo "${item}" | jq -r '.updated_at')
    CLASSIFICATION=$(echo "${item}" | jq -r '.classification')
    OBJECTIVE=$(echo "${item}" | jq -r '.objective')
    SCOPE=$(scope_hint "${CLASSIFICATION}" "${TITLE}" "${LABELS}")
    PRIORITY_VAL=${PRIORITY[${OBJECTIVE}]:-99}

    WORK_ITEMS+=("$(jq -n \
        --arg id "pr-${NUMBER}" \
        --arg type "pr" \
        --argjson number "${NUMBER}" \
        --arg title "${TITLE}" \
        --arg labels "${LABELS}" \
        --arg head_sha "${HEAD_SHA}" \
        --arg updated_at "${UPDATED_AT}" \
        --arg classification "${CLASSIFICATION}" \
        --arg objective "${OBJECTIVE}" \
        --arg scope "${SCOPE}" \
        --argjson priority "${PRIORITY_VAL}" \
        '{id: $id, type: $type, number: $number, title: $title, labels: $labels, head_sha: $head_sha, updated_at: $updated_at, classification: $classification, objective: $objective, scope: $scope, priority: $priority}')")
done <<< "${PR_ITEMS}"

# Process Issues
while IFS= read -r item; do
    [[ -z "${item}" ]] && continue
    COUNTER=$((COUNTER + 1))
    NUMBER=$(echo "${item}" | jq -r '.number')
    TITLE=$(echo "${item}" | jq -r '.title')
    LABELS=$(echo "${item}" | jq -r '.labels')
    UPDATED_AT=$(echo "${item}" | jq -r '.updated_at')
    COMMENTS=$(echo "${item}" | jq -r '.comments')
    CLASSIFICATION=$(echo "${item}" | jq -r '.classification')
    OBJECTIVE=$(echo "${item}" | jq -r '.objective')
    SCOPE=$(scope_hint "${CLASSIFICATION}" "${TITLE}" "${LABELS}")
    PRIORITY_VAL=${PRIORITY[${OBJECTIVE}]:-99}

    WORK_ITEMS+=("$(jq -n \
        --arg id "issue-${NUMBER}" \
        --arg type "issue" \
        --argjson number "${NUMBER}" \
        --arg title "${TITLE}" \
        --arg labels "${LABELS}" \
        --arg updated_at "${UPDATED_AT}" \
        --argjson comments "${COMMENTS}" \
        --arg classification "${CLASSIFICATION}" \
        --arg objective "${OBJECTIVE}" \
        --arg scope "${SCOPE}" \
        --argjson priority "${PRIORITY_VAL}" \
        '{id: $id, type: $type, number: $number, title: $title, labels: $labels, updated_at: $updated_at, comments: $comments, classification: $classification, objective: $objective, scope: $scope, priority: $priority}')")
done <<< "${ISSUE_ITEMS}"

# Optional: refine classification by running triage on metadata (no patch fetch)
if [[ "${REFINE}" == "true" ]]; then
    echo "Refining classifications via triage.sh metadata analysis..." >&2
    # This would fetch each PR's metadata and run triage classification
    # For now, we keep lightweight classification from discover.sh
    # Full triage requires fetch-pr.sh + security-scan.sh + triage.sh per item
    echo "Note: full refinement requires fetch-pr.sh + security-scan.sh + triage.sh per item (not done here)." >&2
fi

# Sort by priority (ascending = higher priority first), then by updated_at (newest first)
# Convert ISO 8601 to epoch seconds for numeric descending sort
# Workaround: sort_by with fromdateiso8601 directly fails, so add epoch field first
# Note: parentheses required around second sort key due to jq operator precedence
SORTED_ITEMS=$(printf '%s\n' "${WORK_ITEMS[@]}" | jq -s 'map(. + {epoch: (.updated_at | fromdateiso8601)}) | sort_by(.priority, (.epoch | -.) ) | map(del(.epoch))')

# Deduplicate by objective: keep highest-priority item per objective
DEDUPED=$(echo "${SORTED_ITEMS}" | jq '
    group_by(.objective) | map(.[0]) | map(. + {epoch: (.updated_at | fromdateiso8601)}) | sort_by(.priority, (.epoch | -.) ) | map(del(.epoch))
')

# Build summary
BY_OBJECTIVE=$(echo "${DEDUPED}" | jq 'group_by(.objective) | map({key: .[0].objective, value: length}) | from_entries')
BY_PRIORITY=$(echo "${DEDUPED}" | jq 'group_by(.priority) | map({key: (.[0].priority | tostring), value: length}) | from_entries')
BY_SCOPE=$(echo "${DEDUPED}" | jq 'group_by(.scope) | map({key: .[0].scope, value: length}) | from_entries')

# Output work queue
TOTAL=$(echo "${DEDUPED}" | jq 'length')
cat > "${OUTPUT_FILE}" <<EOF
{
  "computed_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "source_discovery_status": "${DISCOVERY_STATUS}",
  "work_queue": ${DEDUPED},
  "summary": {
    "total": ${TOTAL},
    "by_objective": ${BY_OBJECTIVE},
    "by_priority": ${BY_PRIORITY},
    "by_scope": ${BY_SCOPE}
  }
}
EOF

echo "=== Work Queue Computed ==="
echo "Total actionable items: ${TOTAL}"
echo "By objective: $(echo "${BY_OBJECTIVE}" | jq -r 'to_entries | map("\(.key):\(.value)") | join(", ")')"
echo "By scope: $(echo "${BY_SCOPE}" | jq -r 'to_entries | map("\(.key):\(.value)") | join(", ")')"
echo "Work queue written: ${OUTPUT_FILE}"
echo
echo "Orchestrator next steps:"
echo "  1. For each item in work_queue (priority order):"
echo "     - oid = item.objective (e.g., OS-UI-COMPONENT)"
echo "     - Check session-reuse: scripts/session-reuse.py find-objective <oid>"
echo "     - If LIVE: resume session with Task task_id=<sid> subagent_type=<worker>"
echo "     - If SESSION_UNAVAILABLE/STALE: fresh Task, then register with --oid <oid>"
echo "  2. Route hardware-profile items to MacBook10,1 profile; core items to generic core"
echo "  3. After queue drained: re-run discover.sh, then proceed to internal objectives"