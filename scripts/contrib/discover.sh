#!/usr/bin/env bash
# discover.sh — Discover new/updated PRs and issues since last run
# Uses gh CLI with scoped token/SSH (no passwords, no creds in repo)
# State stored in lab/contrib/state.json

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_DIR="${REPO_ROOT}/lab/contrib"
STATE_FILE="${STATE_DIR}/state.json"
GH_REPO="${GH_REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo 'owner/repo')}"

mkdir -p "${STATE_DIR}"

# Initialize state file if not exists
if [[ ! -f "${STATE_FILE}" ]]; then
    cat > "${STATE_FILE}" <<'EOF'
{
  "last_pr_check": "1970-01-01T00:00:00Z",
  "last_issue_check": "1970-01-01T00:00:00Z",
  "processed_prs": {},
  "processed_issues": {}
}
EOF
fi

# Read last check timestamps
LAST_PR_CHECK=$(jq -r '.last_pr_check' "${STATE_FILE}")
LAST_ISSUE_CHECK=$(jq -r '.last_issue_check' "${STATE_FILE}")

# Fetch PRs updated since last check
echo "=== Discovering PRs updated since ${LAST_PR_CHECK} ==="
PR_JSON=$(gh pr list --repo "${GH_REPO}" --state all --json number,title,headRefName,baseRefName,headRepository,headRepositoryOwner,author,createdAt,updatedAt,mergedAt,closedAt,commits,additions,deletions,changedFiles,labels,reviewDecision,isDraft --limit 100 2>/dev/null || echo '[]')

# Fetch issues updated since last check
echo "=== Discovering issues updated since ${LAST_ISSUE_CHECK} ==="
ISSUE_JSON=$(gh issue list --repo "${GH_REPO}" --state all --json number,title,state,author,createdAt,updatedAt,closedAt,labels,comments --limit 100 2>/dev/null || echo '[]')

# Process PRs
echo
echo "=== PR Triage Table ==="
printf "%-6s %-12s %-10s %-8s %-8s %-8s %-10s %-30s\n" "NUM" "STATE" "DRAFT" "MERGE" "REVIEW" "+/-" "FILES" "TITLE"
printf "%-6s %-12s %-10s %-8s %-8s %-8s %-10s %-30s\n" "----" "-----" "-----" "----" "------" "---" "-----" "-----"

NEW_PR_CHECK="${LAST_PR_CHECK}"
echo "${PR_JSON}" | jq -c '.[]' | while IFS= read -r pr; do
    NUM=$(echo "${pr}" | jq -r '.number')
    TITLE=$(echo "${pr}" | jq -r '.title' | cut -c1-30)
    STATE=$(echo "${pr}" | jq -r '.state // "UNKNOWN"')
    IS_DRAFT=$(echo "${pr}" | jq -r '.isDraft // false')
    MERGED_AT=$(echo "${pr}" | jq -r '.mergedAt // ""')
    CLOSED_AT=$(echo "${pr}" | jq -r '.closedAt // ""')
    UPDATED_AT=$(echo "${pr}" | jq -r '.updatedAt')
    REVIEW_DECISION=$(echo "${pr}" | jq -r '.reviewDecision // "NONE"')
    ADDITIONS=$(echo "${pr}" | jq -r '.additions // 0')
    DELETIONS=$(echo "${pr}" | jq -r '.deletions // 0')
    CHANGED_FILES=$(echo "${pr}" | jq -r '.changedFiles // 0')
    HEAD_SHA=$(echo "${pr}" | jq -r '.commits[-1].oid // ""')

    # Determine PR display state
    if [[ -n "${MERGED_AT}" && "${MERGED_AT}" != "null" ]]; then
        DISP_STATE="MERGED"
    elif [[ -n "${CLOSED_AT}" && "${CLOSED_AT}" != "null" ]]; then
        DISP_STATE="CLOSED"
    elif [[ "${STATE}" == "OPEN" ]]; then
        DISP_STATE="OPEN"
    else
        DISP_STATE="${STATE}"
    fi

    DRAFT_STR=$([[ "${IS_DRAFT}" == "true" ]] && echo "YES" || echo "NO")
    MERGE_STR=$([[ -n "${MERGED_AT}" && "${MERGED_AT}" != "null" ]] && echo "MERGED" || echo "PENDING")
    REVIEW_STR="${REVIEW_DECISION}"
    STAT_STR="+${ADDITIONS}/-${DELETIONS}"
    FILES_STR="${CHANGED_FILES}f"

    # Check if already processed at this SHA
    PROCESSED_SHA=$(jq -r --arg num "${NUM}" '.processed_prs[$num] // ""' "${STATE_FILE}")
    if [[ "${PROCESSED_SHA}" == "${HEAD_SHA}" && -n "${HEAD_SHA}" ]]; then
        MARK="✓"
    else
        MARK="●"
        # Update newest check time
        if [[ "${UPDATED_AT}" > "${NEW_PR_CHECK}" ]]; then
            NEW_PR_CHECK="${UPDATED_AT}"
        fi
    fi

    printf "%-6s %-12s %-10s %-8s %-8s %-8s %-10s %-30s %s\n" "${NUM}" "${DISP_STATE}" "${DRAFT_STR}" "${MERGE_STR}" "${REVIEW_STR}" "${STAT_STR}" "${FILES_STR}" "${TITLE}" "${MARK}"
done

# Process Issues
echo
echo "=== Issue Triage Table ==="
printf "%-6s %-10s %-10s %-30s\n" "NUM" "STATE" "UPDATED" "TITLE"
printf "%-6s %-10s %-10s %-30s\n" "----" "-----" "-------" "-----"

NEW_ISSUE_CHECK="${LAST_ISSUE_CHECK}"
echo "${ISSUE_JSON}" | jq -c '.[]' | while IFS= read -r issue; do
    NUM=$(echo "${issue}" | jq -r '.number')
    TITLE=$(echo "${issue}" | jq -r '.title' | cut -c1-30)
    STATE=$(echo "${issue}" | jq -r '.state // "UNKNOWN"')
    UPDATED_AT=$(echo "${issue}" | jq -r '.updatedAt')

    MARK="●"
    if [[ "${UPDATED_AT}" > "${NEW_ISSUE_CHECK}" ]]; then
        NEW_ISSUE_CHECK="${UPDATED_AT}"
    fi

    printf "%-6s %-10s %-10s %-30s %s\n" "${NUM}" "${STATE}" "${UPDATED_AT:0:10}" "${TITLE}" "${MARK}"
done

# Update state file with new check times
jq --arg pr_time "${NEW_PR_CHECK}" --arg issue_time "${NEW_ISSUE_CHECK}" \
   '.last_pr_check = $pr_time | .last_issue_check = $issue_time' \
   "${STATE_FILE}" > "${STATE_FILE}.tmp" && mv "${STATE_FILE}.tmp" "${STATE_FILE}"

echo
echo "State updated: ${STATE_FILE}"
echo "Next: run ./scripts/contrib/fetch-pr.sh <PR_NUMBER> to fetch patch for review"