#!/usr/bin/env bash
# fetch-pr.sh — Fetch PR patch, metadata, and file list into review directory
# Usage: fetch-pr.sh <PR_NUMBER>
# Does NOT apply the patch

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REVIEW_BASE="${REPO_ROOT}/lab/contrib/reviews"
GH_REPO="${GH_REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo 'owner/repo')}"

PR_NUMBER="${1:-}"
if [[ -z "${PR_NUMBER}" ]]; then
    echo "Usage: $0 <PR_NUMBER>"
    exit 1
fi

REVIEW_DIR="${REVIEW_BASE}/pr-${PR_NUMBER}-$(date +%Y%m%d-%H%M%S)"
mkdir -p "${REVIEW_DIR}"

echo "=== Fetching PR #${PR_NUMBER} into ${REVIEW_DIR} ==="

# Fetch PR metadata
echo "Fetching metadata..."
gh pr view "${PR_NUMBER}" --repo "${GH_REPO}" --json number,title,body,state,isDraft,headRefName,baseRefName,headRepository,headRepositoryOwner,author,createdAt,updatedAt,mergedAt,closedAt,commits,additions,deletions,changedFiles,labels,reviewDecision,mergeable,mergeStateStatus > "${REVIEW_DIR}/metadata.json"

# Fetch PR commits
echo "Fetching commits..."
gh pr view "${PR_NUMBER}" --repo "${GH_REPO}" --json commits --jq '.commits[] | {oid: .oid, message: .messageHeadline, author: .authors[0].login, date: .committedDate}' > "${REVIEW_DIR}/commits.jsonl"

# Fetch patch/diff
echo "Fetching patch..."
gh pr diff "${PR_NUMBER}" --repo "${GH_REPO}" > "${REVIEW_DIR}/patch.diff"

# Fetch file list with stats
echo "Fetching file list..."
gh pr view "${PR_NUMBER}" --repo "${GH_REPO}" --json files --jq '.files[] | {path: .path, additions: .additions, deletions: .deletions, changeType: .changeType}' > "${REVIEW_DIR}/files.jsonl"

# Fetch reviews
echo "Fetching reviews..."
gh pr view "${PR_NUMBER}" --repo "${GH_REPO}" --json reviews --jq '.reviews[] | {author: .author.login, state: .state, submittedAt: .submittedAt, body: .body}' > "${REVIEW_DIR}/reviews.jsonl" 2>/dev/null || echo '[]' > "${REVIEW_DIR}/reviews.jsonl"

# Fetch check runs (CI status)
echo "Fetching CI status..."
gh pr checks "${PR_NUMBER}" --repo "${GH_REPO}" --json name,conclusion,startedAt,completedAt,detailsUrl > "${REVIEW_DIR}/checks.json" 2>/dev/null || echo '[]' > "${REVIEW_DIR}/checks.json"

# Create summary
cat > "${REVIEW_DIR}/SUMMARY.md" <<EOF
# PR #${PR_NUMBER} Review Package

**Generated:** $(date -u +"%Y-%m-%d %H:%M:%S UTC")
**Repository:** ${GH_REPO}

## Metadata
- **Title:** $(jq -r '.title' "${REVIEW_DIR}/metadata.json")
- **State:** $(jq -r '.state' "${REVIEW_DIR}/metadata.json")
- **Draft:** $(jq -r '.isDraft' "${REVIEW_DIR}/metadata.json")
- **Author:** $(jq -r '.author.login' "${REVIEW_DIR}/metadata.json")
- **Base Branch:** $(jq -r '.baseRefName' "${REVIEW_DIR}/metadata.json")
- **Head Branch:** $(jq -r '.headRefName' "${REVIEW_DIR}/metadata.json")
- **Created:** $(jq -r '.createdAt' "${REVIEW_DIR}/metadata.json")
- **Updated:** $(jq -r '.updatedAt' "${REVIEW_DIR}/metadata.json")
- **Additions:** $(jq -r '.additions' "${REVIEW_DIR}/metadata.json")
- **Deletions:** $(jq -r '.deletions' "${REVIEW_DIR}/metadata.json")
- **Changed Files:** $(jq -r '.changedFiles' "${REVIEW_DIR}/metadata.json")
- **Review Decision:** $(jq -r '.reviewDecision // "NONE"' "${REVIEW_DIR}/metadata.json")
- **Mergeable:** $(jq -r '.mergeable // "UNKNOWN"' "${REVIEW_DIR}/metadata.json")
- **Merge State:** $(jq -r '.mergeStateStatus // "UNKNOWN"' "${REVIEW_DIR}/metadata.json")

## Files Changed
EOF

# Add file list to summary
while IFS= read -r line; do
    PATH=$(echo "${line}" | jq -r '.path')
    ADD=$(echo "${line}" | jq -r '.additions')
    DEL=$(echo "${line}" | jq -r '.deletions')
    TYPE=$(echo "${line}" | jq -r '.changeType')
    echo "- **${PATH}** (+${ADD}/-${DEL}) [${TYPE}]" >> "${REVIEW_DIR}/SUMMARY.md"
done < "${REVIEW_DIR}/files.jsonl"

cat >> "${REVIEW_DIR}/SUMMARY.md" <<EOF

## Commits
EOF

while IFS= read -r line; do
    OID=$(echo "${line}" | jq -r '.oid')
    MSG=$(echo "${line}" | jq -r '.message')
    AUTHOR=$(echo "${line}" | jq -r '.author')
    DATE=$(echo "${line}" | jq -r '.date')
    echo "- \`${OID:0:7}\` **${MSG}** by @${AUTHOR} (${DATE})" >> "${REVIEW_DIR}/SUMMARY.md"
done < "${REVIEW_DIR}/commits.jsonl"

cat >> "${REVIEW_DIR}/SUMMARY.md" <<EOF

## Reviews
EOF

while IFS= read -r line; do
    AUTHOR=$(echo "${line}" | jq -r '.author')
    STATE=$(echo "${line}" | jq -r '.state')
    DATE=$(echo "${line}" | jq -r '.submittedAt')
    BODY=$(echo "${line}" | jq -r '.body // ""' | head -c 100)
    echo "- **${AUTHOR}**: ${STATE} (${DATE}) — ${BODY}" >> "${REVIEW_DIR}/SUMMARY.md"
done < "${REVIEW_DIR}/reviews.jsonl"

cat >> "${REVIEW_DIR}/SUMMARY.md" <<EOF

## CI Checks
EOF

jq -r '.[] | "- \(.name): \(.conclusion // "PENDING")"' "${REVIEW_DIR}/checks.json" >> "${REVIEW_DIR}/SUMMARY.md" 2>/dev/null || echo "No checks data" >> "${REVIEW_DIR}/SUMMARY.md"

echo
echo "=== Review package created: ${REVIEW_DIR} ==="
echo "Contents:"
ls -la "${REVIEW_DIR}/"
echo
echo "Next steps:"
echo "  1. Run security scan: ./scripts/contrib/security-scan.sh ${REVIEW_DIR}"
echo "  2. Run triage:        ./scripts/contrib/triage.sh ${REVIEW_DIR}"
echo "  3. Review SUMMARY.md and patch.diff manually"