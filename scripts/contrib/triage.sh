#!/usr/bin/env bash
# triage.sh — Classify PR/issue and route to review-session objective IDs
# Usage: triage.sh <patchdir>
# Output: classification + objective IDs for review session
#
# Routing model:
#   - REJECTED security verdict → classification "dangerous" (no topical routing)
#   - REQUIRES_SECURITY_REVIEW → adds OS-SEC-REVIEW objective, topical
#     classification still computed normally
#   - Every matching category adds its objective (a PR can route to several
#     review sessions); classification = first (highest-priority) match
#   - File-type refinement only sets classification when text analysis found
#     nothing; it still adds objectives

set -euo pipefail

PATCH_DIR="${1:-}"
if [[ -z "${PATCH_DIR}" || ! -d "${PATCH_DIR}" ]]; then
    echo "Usage: $0 <patch_directory>"
    exit 1
fi

METADATA_FILE="${PATCH_DIR}/metadata.json"
FILES_FILE="${PATCH_DIR}/files.jsonl"
SECURITY_FILE="${PATCH_DIR}/security-scan.json"

if [[ ! -f "${METADATA_FILE}" ]]; then
    echo "ERROR: Metadata not found: ${METADATA_FILE}"
    exit 1
fi

# Read security verdict if available
SEC_VERDICT="UNKNOWN"
if [[ -f "${SECURITY_FILE}" ]]; then
    SEC_VERDICT=$(jq -r '.verdict' "${SECURITY_FILE}")
fi

# Classification categories (from AGENTS.md roadmap priorities)
# irrelev/dup/docs/cosmetic/UI/UX/backend/integration/perf/security/hw/arch/dangerous

CLASSIFICATION=""
CONFIDENCE=0
OBJECTIVE_IDS=()
ROUTE_NOTES=()

# Helper: add objective (deduplicated)
add_objective() {
    local obj="$1"
    local note="$2"
    local existing
    for existing in "${OBJECTIVE_IDS[@]+"${OBJECTIVE_IDS[@]}"}"; do
        [[ "${existing}" == "${obj}" ]] && return 0
    done
    OBJECTIVE_IDS+=("${obj}")
    ROUTE_NOTES+=("${note}")
}

# Helper: set classification only if not yet set
set_classification() {
    local class="$1"
    local confidence="$2"
    if [[ -z "${CLASSIFICATION}" ]]; then
        CLASSIFICATION="${class}"
        CONFIDENCE="${confidence}"
    fi
}

# Analyze metadata
TITLE=$(jq -r '.title' "${METADATA_FILE}")
BODY=$(jq -r '.body // ""' "${METADATA_FILE}")
LABELS=$(jq -r '.labels[].name' "${METADATA_FILE}" 2>/dev/null | tr '\n' ' ' || echo "")
CHANGED_FILES=$(jq -r '.changedFiles // 0' "${METADATA_FILE}")
ADDITIONS=$(jq -r '.additions // 0' "${METADATA_FILE}")
DELETIONS=$(jq -r '.deletions // 0' "${METADATA_FILE}")

# Combine text for analysis
FULL_TEXT="${TITLE} ${BODY} ${LABELS}"
FULL_TEXT_LOWER=$(echo "${FULL_TEXT}" | tr '[:upper:]' '[:lower:]')

echo "=== Triage Analysis: $(basename "${PATCH_DIR}") ==="
echo "Title: ${TITLE}"
echo "Labels: ${LABELS}"
echo "Files: ${CHANGED_FILES} (+${ADDITIONS}/-${DELETIONS})"
echo "Security Verdict: ${SEC_VERDICT}"
echo

# 1. Security override
if [[ "${SEC_VERDICT}" == "REJECTED" ]]; then
    CLASSIFICATION="dangerous"
    CONFIDENCE=100
    add_objective "OS-SEC-REJECT" "Security scan REJECTED — do not test, document reasons"
elif [[ "${SEC_VERDICT}" == "REQUIRES_SECURITY_REVIEW" ]]; then
    add_objective "OS-SEC-REVIEW" "Security scan REQUIRES_REVIEW — manual security audit needed"
fi

# If rejected: no topical routing, go straight to report
if [[ "${CLASSIFICATION}" != "dangerous" ]]; then

# 2. Check for duplicates (simplified - would need issue/PR search in real impl)
if echo "${FULL_TEXT_LOWER}" | grep -qE '(duplicate|dupe|already|existing|fixes #|closes #|resolves #)'; then
    set_classification "dup" 70
    add_objective "OS-DUP-CHECK" "Possible duplicate — verify against existing issues/PRs"
fi

# 3. Documentation only
if echo "${FULL_TEXT_LOWER}" | grep -qE '(\bdoc(s|uation)?\b|readme|changelog|license|contributing|\.md$)'; then
    if [[ ${CHANGED_FILES} -le 5 && ${ADDITIONS} -lt 100 ]]; then
        set_classification "docs" 80
        add_objective "OS-DOCS" "Documentation-only change — quick review"
    fi
fi

# 4. Cosmetic/UI only (theme, colors, icons, spacing)
if echo "${FULL_TEXT_LOWER}" | grep -qE '(cosmetic|theme|color|icon|font|spacing|margin|padding|visual|style|css|gtk.*theme)'; then
    set_classification "cosmetic" 75
    add_objective "OS-UI-COSMETIC" "Cosmetic/UI theme change — visual regression test"
fi

# 5. UX/Interaction changes
if echo "${FULL_TEXT_LOWER}" | grep -qE '(\bux\b|user.experience|interaction|shortcut|hotkey|keybind|menu|dialog|workflow|flow|usability)'; then
    set_classification "UX" 75
    add_objective "OS-UX" "UX/interaction change — behavior review needed"
fi

# 6. UI component changes (new widgets, panels, windows)
if echo "${FULL_TEXT_LOWER}" | grep -qE '(\bui\b|widget|panel|window|dialog|sidebar|toolbar|overlay|launcher|dock|menu.bar)'; then
    set_classification "UI" 70
    add_objective "OS-UI-COMPONENT" "UI component change — integration review"
fi

# 7. Integration changes (between components) — checked before backend:
# cross-component signals (sync/bridge/hook) are more specific than generic
# backend keywords (service/daemon) which appear in almost any PR
if echo "${FULL_TEXT_LOWER}" | grep -qE '(integrat|connect|bridge|hook|signal|dbus|ipc|pipe|sync)'; then
    set_classification "integration" 70
    add_objective "OS-INTEGRATION" "Integration change — cross-component test"
fi

# 8. Backend/core logic changes
if echo "${FULL_TEXT_LOWER}" | grep -qE '(backend|core|engine|daemon|service|database|storage|index|search|plocate|rofi|thunar)'; then
    set_classification "backend" 70
    add_objective "OS-BACKEND" "Backend logic change — functional + regression test"
fi

# 9. Performance-related
if echo "${FULL_TEXT_LOWER}" | grep -qE '(perf|performance|speed|latency|memory|cpu|battery|power|energy|optimiz)'; then
    set_classification "perf" 70
    add_objective "OS-PERF" "Performance change — benchmark required"
fi

# 10. Hardware-specific
if echo "${FULL_TEXT_LOWER}" | grep -qE '(hardware|macbook|apple|spi|i2c|gpio|acpi|firmware|bcm43602|cirrus|nvme|s3x|applespi|trackpad|keyboard|wifi|audio|bluetooth|brightness|thermal|fan)'; then
    set_classification "hw" 80
    add_objective "OS-HW" "Hardware-specific change — requires hardware validation"
fi

# 11. Architecture/infrastructure
if echo "${FULL_TEXT_LOWER}" | grep -qE '(architect|infra|build|\bci\b|\bcd\b|pipeline|\biso\b|archiso|package|pacman|dkms|kernel|initramfs|bootloader|systemd)'; then
    set_classification "arch" 75
    add_objective "OS-ARCH" "Architecture/infrastructure change — build + boot test"
fi

# 12. Irrelevant/out of scope
if echo "${FULL_TEXT_LOWER}" | grep -qE '(wontfix|wont.fix|out.of.scope|irrelevant|not.needed|deferred|exclude)'; then
    set_classification "irrelev" 60
    add_objective "OS-IRRELEV" "Marked irrelevant/out of scope — document reason"
fi

# Default classification if none matched
if [[ -z "${CLASSIFICATION}" ]]; then
    CLASSIFICATION="backend"
    CONFIDENCE=40
    add_objective "OS-GENERIC" "Unclassified — generic backend review"
fi

# File-type based refinement (objectives always; classification only if unset)
echo "Analyzing changed files..."
if [[ -f "${FILES_FILE}" ]] && [[ -s "${FILES_FILE}" ]]; then
    while IFS= read -r line; do
        F_PATH=$(echo "${line}" | jq -r '.path')
        case "${F_PATH}" in
            *.md|*.txt|*.rst|LICENSE*|COPYING*|AUTHORS*|CONTRIBUTING*)
                add_objective "OS-DOCS" "Documentation file changed"
                set_classification "docs" 85
                ;;
            *.css|*.scss|*.theme|*gtk*|*icon*|*cursor*|*wallpaper*)
                add_objective "OS-UI-COSMETIC" "Visual asset changed"
                set_classification "cosmetic" 80
                ;;
            *.desktop|*autostart*)
                add_objective "OS-INTEGRATION" "Desktop integration file changed"
                set_classification "integration" 75
                ;;
            *systemd*|*.service|*.socket|*.timer|*.mount)
                add_objective "OS-ARCH" "systemd unit changed"
                set_classification "arch" 85
                ;;
            *udev*|*rules.d*)
                add_objective "OS-HW" "udev rule changed"
                set_classification "hw" 85
                ;;
            *kernel*|*dkms*|*modprobe*)
                add_objective "OS-HW" "Kernel/DKMS component changed"
                set_classification "hw" 90
                ;;
            PKGBUILD|*/PKGBUILD)
                add_objective "OS-ARCH" "PKGBUILD build recipe changed"
                set_classification "arch" 80
                ;;
            scripts/contrib/*)
                add_objective "OS-ARCH" "Contribution pipeline changed"
                set_classification "arch" 90
                ;;
            lab/harness/*|lab/tests/*)
                add_objective "OS-ARCH" "Lab harness/test changed"
                set_classification "arch" 85
                ;;
            *) ;;
        esac
    done < "${FILES_FILE}"
fi

fi # end non-dangerous block

# Output results
REPORT_FILE="${PATCH_DIR}/triage.json"
cat > "${REPORT_FILE}" <<EOF
{
  "patch_dir": "${PATCH_DIR}",
  "triaged_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "classification": "${CLASSIFICATION}",
  "confidence": ${CONFIDENCE},
  "security_verdict": "${SEC_VERDICT}",
  "objectives": $(printf '%s\n' "${OBJECTIVE_IDS[@]}" | jq -R . | jq -s .),
  "route_notes": $(printf '%s\n' "${ROUTE_NOTES[@]}" | jq -R . | jq -s .),
  "metadata": {
    "title": "${TITLE}",
    "changed_files": ${CHANGED_FILES},
    "additions": ${ADDITIONS},
    "deletions": ${DELETIONS}
  }
}
EOF

echo
echo "=== Triage Result ==="
echo "Classification: ${CLASSIFICATION} (confidence: ${CONFIDENCE}%)"
echo "Security: ${SEC_VERDICT}"
echo "Objectives:"
for i in "${!OBJECTIVE_IDS[@]}"; do
    echo "  ${OBJECTIVE_IDS[$i]} — ${ROUTE_NOTES[$i]}"
done
echo
echo "Report saved: ${REPORT_FILE}"

# Next steps hint
echo
echo "Next steps based on classification:"
case "${CLASSIFICATION}" in
    dangerous)
        echo "  → REJECTED by security scan. Document in REJECTED log, close PR."
        ;;
    security)
        echo "  → Requires manual security audit. Assign to security reviewer."
        ;;
    dup)
        echo "  → Verify duplicate, link to original, close if confirmed."
        ;;
    docs)
        echo "  → Quick review, merge if accurate."
        ;;
    cosmetic|UI|UX)
        echo "  → Visual/behavior review. Screenshot comparison in QEMU."
        ;;
    backend|integration|perf)
        echo "  → Functional test in isolated build agent. Run regression suite."
        ;;
    hw)
        echo "  → Mark NEEDS_HARDWARE_TEST. Queue for hardware validation."
        ;;
    arch)
        echo "  → Build ISO, boot test in QEMU, verify no regression."
        ;;
    irrelev)
        echo "  → Close with explanation."
        ;;
    *)
        echo "  → Generic review pipeline."
        ;;
esac
