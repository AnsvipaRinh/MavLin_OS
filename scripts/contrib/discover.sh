#!/usr/bin/env bash
# discover.sh — Discover new/updated PRs and issues since last run
# Uses gh CLI with scoped token/SSH (no passwords, no creds in repo)
# State stored in lab/contrib/state.json
# Output: human-readable tables + machine-readable lab/contrib/backlog.json
# Exit codes: 0=OK, 1=gh failure (UNAVAILABLE), 2=auth invalid, 3=rate limited

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_DIR="${REPO_ROOT}/lab/contrib"
STATE_FILE="${STATE_DIR}/state.json"
BACKLOG_FILE="${STATE_DIR}/backlog.json"
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

# Repo provenance: reset processed maps if state was built for a different repo
# (prevents stale/cross-repo state from silently producing EMPTY)
STATE_REPO=$(jq -r '.repo // ""' "${STATE_FILE}")
if [[ -n "${STATE_REPO}" && "${STATE_REPO}" != "${GH_REPO}" ]]; then
    echo "WARNING: state repo (${STATE_REPO}) != discovered repo (${GH_REPO}); resetting processed maps"
    jq '.processed_prs = {} | .processed_issues = {}' "${STATE_FILE}" > "${STATE_FILE}.tmp" && mv "${STATE_FILE}.tmp" "${STATE_FILE}"
fi

# Fetch PRs updated since last check
echo "=== Discovering PRs updated since ${LAST_PR_CHECK} ==="
PR_JSON=""
PR_STDERR=""
if ! PR_JSON=$(gh pr list --repo "${GH_REPO}" --state all --json number,title,headRefName,baseRefName,headRepository,headRepositoryOwner,author,createdAt,updatedAt,mergedAt,closedAt,headRefOid,additions,deletions,changedFiles,labels,reviewDecision,isDraft --limit 100 2>"${STATE_DIR}/gh_pr.stderr"); then
    PR_STDERR=$(cat "${STATE_DIR}/gh_pr.stderr" 2>/dev/null || echo "gh pr list failed")
    echo "ERROR: gh pr list failed: ${PR_STDERR}"
    # Classify failure
    if echo "${PR_STDERR}" | grep -qi "authentication\|unauthorized\|401\|token\|login"; then
        DISCOVERY_STATUS="AUTH_INVALID"
        EXIT_CODE=2
    elif echo "${PR_STDERR}" | grep -qi "rate limit\|429\|too many requests"; then
        DISCOVERY_STATUS="RATE_LIMITED"
        EXIT_CODE=3
    else
        DISCOVERY_STATUS="UNAVAILABLE"
        EXIT_CODE=1
    fi
    PR_JSON="[]"
fi

# Fetch issues updated since last check
echo "=== Discovering issues updated since ${LAST_ISSUE_CHECK} ==="
ISSUE_JSON=""
ISSUE_STDERR=""
if ! ISSUE_JSON=$(gh issue list --repo "${GH_REPO}" --state all --json number,title,state,author,createdAt,updatedAt,closedAt,labels,comments --limit 100 2>"${STATE_DIR}/gh_issue.stderr"); then
    ISSUE_STDERR=$(cat "${STATE_DIR}/gh_issue.stderr" 2>/dev/null || echo "gh issue list failed")
    echo "ERROR: gh issue list failed: ${ISSUE_STDERR}"
    # Classify failure (if PR already failed, keep that status)
    if [[ -z "${DISCOVERY_STATUS:-}" ]]; then
        if echo "${ISSUE_STDERR}" | grep -qi "authentication\|unauthorized\|401\|token\|login"; then
            DISCOVERY_STATUS="AUTH_INVALID"
            EXIT_CODE=2
        elif echo "${ISSUE_STDERR}" | grep -qi "rate limit\|429\|too many requests"; then
            DISCOVERY_STATUS="RATE_LIMITED"
            EXIT_CODE=3
        else
            DISCOVERY_STATUS="UNAVAILABLE"
            EXIT_CODE=1
        fi
    fi
    ISSUE_JSON="[]"
fi

# If both succeeded and no explicit failure status
if [[ -z "${DISCOVERY_STATUS:-}" ]]; then
    DISCOVERY_STATUS="OK"
    EXIT_CODE=0
fi

# Raw fetched counts (auditability: EMPTY is only truthful if these match reality)
GH_PR_COUNT=$(echo "${PR_JSON}" | jq 'length')
GH_ISSUE_COUNT=$(echo "${ISSUE_JSON}" | jq 'length')

# Process PRs
echo
echo "=== PR Triage Table ==="
printf "%-6s %-12s %-10s %-8s %-8s %-8s %-10s %-30s\n" "NUM" "STATE" "DRAFT" "MERGE" "REVIEW" "+/-" "FILES" "TITLE"
printf "%-6s %-12s %-10s %-8s %-8s %-8s %-10s %-30s\n" "----" "-----" "-----" "----" "------" "---" "-----" "-----"

NEW_PR_CHECK="${LAST_PR_CHECK}"
PR_BACKLOG=()
while IFS= read -r pr; do
    NUM=$(echo "${pr}" | jq -r '.number')
    FULL_TITLE=$(echo "${pr}" | jq -r '.title')
    TITLE=$(echo "${FULL_TITLE}" | cut -c1-30)
    STATE=$(echo "${pr}" | jq -r '.state // "UNKNOWN"')
    IS_DRAFT=$(echo "${pr}" | jq -r '.isDraft // false')
    MERGED_AT=$(echo "${pr}" | jq -r '.mergedAt // ""')
    CLOSED_AT=$(echo "${pr}" | jq -r '.closedAt // ""')
    UPDATED_AT=$(echo "${pr}" | jq -r '.updatedAt')
    REVIEW_DECISION=$(echo "${pr}" | jq -r '.reviewDecision // "NONE"')
    ADDITIONS=$(echo "${pr}" | jq -r '.additions // 0')
    DELETIONS=$(echo "${pr}" | jq -r '.deletions // 0')
    CHANGED_FILES=$(echo "${pr}" | jq -r '.changedFiles // 0')
    HEAD_SHA=$(echo "${pr}" | jq -r '.headRefOid // ""')
    LABELS=$(echo "${pr}" | jq -r '.labels[].name' 2>/dev/null | tr '\n' ',' | sed 's/,$//' || echo "")

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
        PROCESSED="true"
    else
        MARK="●"
        PROCESSED="false"
        # Update newest check time
        if [[ "${UPDATED_AT}" > "${NEW_PR_CHECK}" ]]; then
            NEW_PR_CHECK="${UPDATED_AT}"
        fi
    fi

    printf "%-6s %-12s %-10s %-8s %-8s %-8s %-10s %-30s %s\n" "${NUM}" "${DISP_STATE}" "${DRAFT_STR}" "${MERGE_STR}" "${REVIEW_STR}" "${STAT_STR}" "${FILES_STR}" "${TITLE}" "${MARK}"

    # Build backlog entry for unprocessed OPEN PRs
    if [[ "${PROCESSED}" == "false" && "${DISP_STATE}" == "OPEN" ]]; then
        # Lightweight classification from metadata
        CLASSIFICATION=$(echo "${FULL_TITLE} ${LABELS}" | tr '[:upper:]' '[:lower:]' | \
            awk '{
                if (/cosmetic|theme|color|icon|font|spacing|visual|style|css|gtk.*theme/) print "cosmetic";
                else if (/ux|user.experience|interaction|shortcut|hotkey|keybind|menu|dialog|workflow|flow|usability/) print "UX";
                else if (/ui|widget|panel|window|dialog|sidebar|toolbar|overlay|launcher|dock|menu.bar/) print "UI";
                else if (/integrat|connect|bridge|hook|signal|dbus|ipc|pipe|sync/) print "integration";
                else if (/backend|core|engine|daemon|service|database|storage|index|search|plocate|rofi|thunar/) print "backend";
                else if (/perf|performance|speed|latency|memory|cpu|battery|power|energy|optimiz/) print "perf";
                else if (/hardware|macbook|apple|spi|i2c|gpio|acpi|firmware|bcm43602|cirrus|nvme|s3x|applespi|trackpad|keyboard|wifi|audio|bluetooth|brightness|thermal|fan/) print "hw";
                else if (/architect|infra|build|ci|cd|pipeline|iso|archiso|package|pacman|dkms|kernel|initramfs|bootloader|systemd/) print "arch";
                else if (/doc|readme|changelog|license|contributing/) print "docs";
                else print "backend";
            }')
        OBJECTIVE=$(case "${CLASSIFICATION}" in
            cosmetic) echo "OS-UI-COSMETIC" ;;
            UX) echo "OS-UX" ;;
            UI) echo "OS-UI-COMPONENT" ;;
            integration) echo "OS-INTEGRATION" ;;
            backend) echo "OS-BACKEND" ;;
            perf) echo "OS-PERF" ;;
            hw) echo "OS-HW" ;;
            arch) echo "OS-ARCH" ;;
            docs) echo "OS-DOCS" ;;
            *) echo "OS-GENERIC" ;;
        esac)
        PR_BACKLOG+=("{\"type\":\"pr\",\"number\":${NUM},\"title\":\"$(echo "${pr}" | jq -r '.title' | sed 's/"/\\"/g')\",\"labels\":\"${LABELS}\",\"head_sha\":\"${HEAD_SHA}\",\"updated_at\":\"${UPDATED_AT}\",\"classification\":\"${CLASSIFICATION}\",\"objective\":\"${OBJECTIVE}\"}")
    fi
done < <(echo "${PR_JSON}" | jq -c '.[]')

# Process Issues
echo
echo "=== Issue Triage Table ==="
printf "%-6s %-10s %-10s %-30s\n" "NUM" "STATE" "UPDATED" "TITLE"
printf "%-6s %-10s %-10s %-30s\n" "----" "-----" "-------" "-----"

NEW_ISSUE_CHECK="${LAST_ISSUE_CHECK}"
ISSUE_BACKLOG=()
while IFS= read -r issue; do
    NUM=$(echo "${issue}" | jq -r '.number')
    FULL_TITLE=$(echo "${issue}" | jq -r '.title')
    TITLE=$(echo "${FULL_TITLE}" | cut -c1-30)
    STATE=$(echo "${issue}" | jq -r '.state // "UNKNOWN"')
    UPDATED_AT=$(echo "${issue}" | jq -r '.updatedAt')
    LABELS=$(echo "${issue}" | jq -r '.labels[].name' 2>/dev/null | tr '\n' ',' | sed 's/,$//' || echo "")
    COMMENTS_COUNT=$(echo "${issue}" | jq -r '(.comments // []) | length')

    MARK="●"
    PROCESSED="false"
    PROCESSED_SHA=$(jq -r --arg num "${NUM}" '.processed_issues[$num] // ""' "${STATE_FILE}")
    # Issues don't have SHA, use updatedAt as proxy
    if [[ "${PROCESSED_SHA}" == "${UPDATED_AT}" && -n "${UPDATED_AT}" ]]; then
        MARK="✓"
        PROCESSED="true"
    else
        if [[ "${UPDATED_AT}" > "${NEW_ISSUE_CHECK}" ]]; then
            NEW_ISSUE_CHECK="${UPDATED_AT}"
        fi
    fi

    printf "%-6s %-10s %-10s %-30s %s\n" "${NUM}" "${STATE}" "${UPDATED_AT:0:10}" "${TITLE}" "${MARK}"

    # Build backlog entry for unprocessed OPEN issues
    if [[ "${PROCESSED}" == "false" && "${STATE}" == "OPEN" ]]; then
        CLASSIFICATION=$(echo "${FULL_TITLE} ${LABELS}" | tr '[:upper:]' '[:lower:]' | \
            awk '{
                if (/cosmetic|theme|color|icon|font|spacing|visual|style|css|gtk.*theme/) print "cosmetic";
                else if (/ux|user.experience|interaction|shortcut|hotkey|keybind|menu|dialog|workflow|flow|usability/) print "UX";
                else if (/ui|widget|panel|window|dialog|sidebar|toolbar|overlay|launcher|dock|menu.bar/) print "UI";
                else if (/integrat|connect|bridge|hook|signal|dbus|ipc|pipe|sync/) print "integration";
                else if (/backend|core|engine|daemon|service|database|storage|index|search|plocate|rofi|thunar/) print "backend";
                else if (/perf|performance|speed|latency|memory|cpu|battery|power|energy|optimiz/) print "perf";
                else if (/hardware|macbook|apple|spi|i2c|gpio|acpi|firmware|bcm43602|cirrus|nvme|s3x|applespi|trackpad|keyboard|wifi|audio|bluetooth|brightness|thermal|fan/) print "hw";
                else if (/architect|infra|build|ci|cd|pipeline|iso|archiso|package|pacman|dkms|kernel|initramfs|bootloader|systemd/) print "arch";
                else if (/doc|readme|changelog|license|contributing/) print "docs";
                else print "backend";
            }')
        OBJECTIVE=$(case "${CLASSIFICATION}" in
            cosmetic) echo "OS-UI-COSMETIC" ;;
            UX) echo "OS-UX" ;;
            UI) echo "OS-UI-COMPONENT" ;;
            integration) echo "OS-INTEGRATION" ;;
            backend) echo "OS-BACKEND" ;;
            perf) echo "OS-PERF" ;;
            hw) echo "OS-HW" ;;
            arch) echo "OS-ARCH" ;;
            docs) echo "OS-DOCS" ;;
            *) echo "OS-GENERIC" ;;
        esac)
        ISSUE_BACKLOG+=("{\"type\":\"issue\",\"number\":${NUM},\"title\":\"$(echo "${issue}" | jq -r '.title' | sed 's/"/\\"/g')\",\"labels\":\"${LABELS}\",\"updated_at\":\"${UPDATED_AT}\",\"comments\":${COMMENTS_COUNT},\"classification\":\"${CLASSIFICATION}\",\"objective\":\"${OBJECTIVE}\"}")
    fi
done < <(echo "${ISSUE_JSON}" | jq -c '.[]')

# Update state file with new check times + repo provenance
jq --arg pr_time "${NEW_PR_CHECK}" --arg issue_time "${NEW_ISSUE_CHECK}" --arg repo "${GH_REPO}" \
   '.last_pr_check = $pr_time | .last_issue_check = $issue_time | .repo = $repo' \
   "${STATE_FILE}" > "${STATE_FILE}.tmp" && mv "${STATE_FILE}.tmp" "${STATE_FILE}"

# Build machine-readable backlog.json
BACKLOG_COUNT=$((${#PR_BACKLOG[@]} + ${#ISSUE_BACKLOG[@]}))
if [[ "${DISCOVERY_STATUS}" == "OK" && ${BACKLOG_COUNT} -eq 0 ]]; then
    DISCOVERY_STATUS="EMPTY"
fi

# Combine backlog arrays into JSON
PR_JSON_ARRAY=$(printf '%s\n' "${PR_BACKLOG[@]}" | jq -s .)
ISSUE_JSON_ARRAY=$(printf '%s\n' "${ISSUE_BACKLOG[@]}" | jq -s .)

cat > "${BACKLOG_FILE}" <<EOF
{
  "discovered_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "discovery_status": "${DISCOVERY_STATUS}",
  "exit_code": ${EXIT_CODE},
  "pr_count": ${#PR_BACKLOG[@]},
  "issue_count": ${#ISSUE_BACKLOG[@]},
  "total_count": ${BACKLOG_COUNT},
  "gh_pr_count": ${GH_PR_COUNT},
  "gh_issue_count": ${GH_ISSUE_COUNT},
  "prs": ${PR_JSON_ARRAY},
  "issues": ${ISSUE_JSON_ARRAY},
  "objectives": $(printf '%s\n' "${PR_BACKLOG[@]}" "${ISSUE_BACKLOG[@]}" | jq -s '.[].objective' | sort -u | jq -s .)
}
EOF

echo
echo "State updated: ${STATE_FILE}"
echo "Backlog written: ${BACKLOG_FILE}"
echo "Discovery status: ${DISCOVERY_STATUS} (exit code: ${EXIT_CODE})"
echo "Backlog items: ${BACKLOG_COUNT} (PRs: ${#PR_BACKLOG[@]}, Issues: ${#ISSUE_BACKLOG[@]})"
if [[ ${BACKLOG_COUNT} -gt 0 ]]; then
    echo "Objectives: $(jq -r '.objectives | join(", ")' "${BACKLOG_FILE}")"
fi

echo
if [[ "${DISCOVERY_STATUS}" != "OK" && "${DISCOVERY_STATUS}" != "EMPTY" ]]; then
    echo "=== GitHub discovery failed: ${DISCOVERY_STATUS} ==="
    echo "Orchestrator should classify and apply retry policy before continuing internal work."
elif [[ "${DISCOVERY_STATUS}" == "EMPTY" ]]; then
    echo "=== No actionable external contributions ==="
    echo "Orchestrator may proceed to internal self-improvement objectives."
else
    echo "=== Actionable external contribution backlog found ==="
    echo "Orchestrator should route items to Build workers via session-reuse (oid = objective)."
fi
echo "Next: run ./scripts/contrib/backlog.sh to compute prioritized work queue, or fetch-pr.sh <PR_NUMBER> for full review."

exit ${EXIT_CODE}