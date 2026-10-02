#!/usr/bin/env bash
# security-scan.sh — Static security analysis of PR patch
# Usage: security-scan.sh <patchdir>
# NEVER executes contributor code — only static analysis.
# Output: verdict (SAFE_TO_TEST / REQUIRES_SECURITY_REVIEW / REJECTED) + reasons.
#
# Calibration notes:
#   - Patterns are word-boundary anchored to avoid false positives
#     (e.g. "sh " must not match "push ", "dd " must not match "add ").
#   - Redirect detection excludes XML self-closing tags ("/>").
#   - Documentation-only patches (all changed files .md/.txt/...) skip
#     code-execution categories: fenced code blocks in docs are not
#     executed code. Credential/path-traversal/binary checks still run.
#   - Relative "../" references are NOT path traversal by themselves;
#     traversal requires co-occurrence with archive extraction or
#     concatenated file-open calls.

set -euo pipefail
export PATH="/usr/sbin:/usr/bin:/bin:/sbin:$PATH"

PATCH_DIR="${1:-}"
if [[ -z "${PATCH_DIR}" || ! -d "${PATCH_DIR}" ]]; then
    echo "Usage: $0 <patch_directory>"
    exit 1
fi

PATCH_FILE="${PATCH_DIR}/patch.diff"
METADATA_FILE="${PATCH_DIR}/metadata.json"
FILES_FILE="${PATCH_DIR}/files.jsonl"

if [[ ! -f "${PATCH_FILE}" ]]; then
    echo "ERROR: Patch file not found: ${PATCH_FILE}"
    exit 1
fi

VERDICT="SAFE_TO_TEST"
REASONS=()
HIGH_RISK=0
MED_RISK=0
LOW_RISK=0

add_finding() {
    local level="$1"
    local category="$2"
    local detail="$3"
    REASONS+=("[${level}] ${category}: ${detail}")
    case "${level}" in
        HIGH) ((HIGH_RISK+=1)) ;;
        MED) ((MED_RISK+=1)) ;;
        LOW) ((LOW_RISK+=1)) ;;
    esac
}

finalize_verdict() {
    if [[ ${HIGH_RISK} -gt 0 ]]; then
        VERDICT="REJECTED"
    elif [[ ${MED_RISK} -gt 0 ]]; then
        VERDICT="REQUIRES_SECURITY_REVIEW"
    fi
}

# Added code lines (exclude +++ headers and pure comment lines)
ADDED_LINES='^+[^+]'
IS_COMMENT='^+[[:space:]]*#'

added() { /usr/bin/grep "${ADDED_LINES}" "${PATCH_FILE}" 2>/dev/null || true; }
added_code() { added | /usr/bin/grep -v "${IS_COMMENT}" 2>/dev/null || true; }

# Classify patch by changed file list (files.jsonl)
DOC_ONLY=true
HAS_CODE=false
HAS_PKGBUILD=false
if [[ -f "${FILES_FILE}" ]] && [[ -s "${FILES_FILE}" ]]; then
    while IFS= read -r line; do
        P=$(/usr/sbin/jq -r '.path // empty' <<< "${line}" 2>/dev/null || true)
        [[ -z "${P}" ]] && continue
        case "${P}" in
            *.md|*.txt|*.rst|*.adoc|*.markdown) ;;
            PKGBUILD|*/PKGBUILD) HAS_PKGBUILD=true; DOC_ONLY=false; HAS_CODE=true ;;
            *.sh|*.bash|*.service|*.socket|*.timer|*.mount|*.automount|*.target|*.path|\
            *.hook|*.install|*.py|*.pl|*.rb|*.js|*.c|*.h|*.cc|*.cpp|*.go|*.rs)
                DOC_ONLY=false; HAS_CODE=true ;;
            *) DOC_ONLY=false ;;
        esac
    done < "${FILES_FILE}"
fi
# Empty/missing files.jsonl → conservative full scan
if [[ ! -f "${FILES_FILE}" || ! -s "${FILES_FILE}" ]]; then
    DOC_ONLY=false; HAS_CODE=true
fi

echo "=== Security Scan: ${PATCH_DIR} ==="
echo "Patch: $(basename "${PATCH_DIR}")"
echo "Classification: doc_only=${DOC_ONLY} code=${HAS_CODE} pkgbuild=${HAS_PKGBUILD}"
echo

# Helper: run a check only for code-bearing patches
code_check() { [[ "${HAS_CODE}" == "true" ]]; }

# 1. Shell/subprocess execution
echo "[1/14] Checking shell/subprocess execution..."
if code_check; then
    # HIGH: eval, backticks, download|interpreter, relative script exec, source .sh
    if added_code | /usr/bin/grep -E '\beval\b(\s|$)|`[^`]+`|\|[[:space:]]*\b(bash|sh|zsh|dash|python3?|perl|ruby|node)\b|\./[A-Za-z0-9_-]+\.(sh|bash|py|pl|rb|js)\b|\bsource\b[[:space:]]+\S+\.(sh|bash)\b' >/dev/null 2>&1; then
        add_finding "HIGH" "SHELL_EXEC" "Added code contains eval, backtick execution, download piped to interpreter, or relative script execution"
    # MED: command substitution, bare interpreter invocation
    elif added_code | /usr/bin/grep -E '\$\(|\b(bash|sh|zsh|dash|python3?|perl|ruby|node)\b(\s|$)' >/dev/null 2>&1; then
        add_finding "MED" "SHELL_EXEC" "Added code contains command substitution or interpreter invocation (review input handling)"
    fi
fi

# 2. Filesystem writes outside allowed paths
echo "[2/14] Checking filesystem writes..."
if [[ "${DOC_ONLY}" != "true" ]]; then
    if added_code | /usr/bin/grep -E '\b(tee|dd|cp|mv|install|mkdir|rm|rmdir|chmod|chown|chattr|ln|cat)\b[[:space:]]|(^|[^/<?>&|])>>?[[:space:]]*(/|~|\$|\./|\.\./)' | /usr/bin/grep -v "${IS_COMMENT}" >/dev/null 2>&1; then
        add_finding "MED" "FS_WRITE" "Added code writes to filesystem (redirection, copy, removal, or install outside temp paths)"
    fi
fi

# 3. Privilege escalation patterns
echo "[3/14] Checking privilege escalation..."
if code_check; then
    if added_code | /usr/bin/grep -E '\b(sudo|su|doas|pkexec)\b(\s|$)|set(id|gid|euid|egid)\b|capabilities\b|cap_set\b' >/dev/null 2>&1; then
        add_finding "HIGH" "PRIV_ESCALATION" "Added code contains privilege escalation patterns (sudo, su, setuid, capabilities)"
    fi
fi

# 4. systemd/unit file modifications
echo "[4/14] Checking systemd/unit modifications..."
if added | /usr/bin/grep -E '\.(service|socket|timer|mount|automount|target|path)\b' >/dev/null 2>&1; then
    add_finding "MED" "SYSTEMD_UNIT" "Added code references or modifies systemd unit files"
fi

# 5. udev rules
echo "[5/14] Checking udev rules..."
if added | /usr/bin/grep -E 'rules\.d\b|ATTR\{|SUBSYSTEM==|KERNEL==|ACTION==|RUN\+=|\budev\b(\s|$)' >/dev/null 2>&1; then
    add_finding "MED" "UDEV_RULES" "Added code contains udev rule patterns"
fi

# 6. Network operations
echo "[6/14] Checking network operations..."
if code_check; then
    if added_code | /usr/bin/grep -E '\b(curl|wget|nc|netcat|socat|ssh|scp|rsync|ftp|telnet)\b(\s|$)|/dev/(tcp|udp)|socket[[:space:]]*\(|connect[[:space:]]*\(' >/dev/null 2>&1; then
        add_finding "MED" "NETWORK_OPS" "Added code contains network operations (curl, wget, ssh, sockets, etc.)"
    fi
fi

# 7. Downloads/remote code fetch
echo "[7/14] Checking downloads/remote fetch..."
if code_check; then
    if added_code | /usr/bin/grep -E '\b(curl|wget)\b.*\||\b(curl|wget)\b.*-[a-zA-Z]*[Oo]|\bgit[[:space:]]+(clone|pull)\b|\b(fetch|download)\S*[[:space:]].*https?://' >/dev/null 2>&1; then
        add_finding "HIGH" "REMOTE_FETCH" "Added code downloads content from remote URLs (supply-chain risk)"
    fi
fi

# 8. Package installation
echo "[8/14] Checking package installation..."
if code_check; then
    if added_code | /usr/bin/grep -E '\b(pacman|apt|apt-get|yum|dnf|zypper|apk|pip|pip3|npm|gem|cargo)\b[[:space:]]|\bgo[[:space:]]+get\b|\bmake[[:space:]]+install\b' >/dev/null 2>&1; then
        add_finding "HIGH" "PKG_INSTALL" "Added code installs packages via package managers"
    fi
fi

# 9. Credential/environment variable exposure
echo "[9/14] Checking credential/secret exposure..."
if added_code | /usr/bin/grep -E '\$\{?(AWS|GITHUB|DOCKER|NPM|PYPI|GITLAB)_[A-Z_]+|\b(password|passwd|secret|token|api_key|apikey|private_key|ssh_key)[[:space:]]*[:=]' >/dev/null 2>&1; then
    add_finding "HIGH" "CRED_EXPOSURE" "Added code references potential credentials/secrets or secret environment variables"
fi

# 10. Persistence/autostart mechanisms
echo "[10/14] Checking persistence/autostart..."
if added | /usr/bin/grep -E '\.desktop\b|\bautostart\b|\bsystemctl[[:space:]]+enable\b|\brc\.local\b|\bcrontab\b|\bat[[:space:]]+(now|[0-9]|daily|weekly|hourly)\b|\bupdate-rc\.d\b|\bchkconfig\b' >/dev/null 2>&1; then
    add_finding "MED" "PERSISTENCE" "Added code configures persistence/autostart mechanisms"
fi

# 11. D-Bus/PolicyKit interactions
echo "[11/14] Checking D-Bus/Polkit..."
if added | /usr/bin/grep -E '\b(dbus-send|gdbus|pkexec|pkcheck|pkaction|polkit)\b' >/dev/null 2>&1; then
    add_finding "MED" "DBUS_POLKIT" "Added code interacts with D-Bus or PolicyKit"
fi

# 12. Kernel module/parameters
echo "[12/14] Checking kernel interactions..."
if added | /usr/bin/grep -E '\b(modprobe|insmod|rmmod|lsmod|sysctl)\b(\s|$)|/proc/|/sys/module|/sys/kernel' >/dev/null 2>&1; then
    add_finding "MED" "KERNEL_OPS" "Added code interacts with kernel modules or parameters"
fi

# 13. Unsafe parsing/deserialization
echo "[13/14] Checking unsafe parsing..."
if code_check; then
    if added_code | /usr/bin/grep -E '\beval[[:space:]]*\(|\bexec[[:space:]]*\(|pickle\.loads\b|yaml\.load[[:space:]]*\(|marshal\.loads\b|shelve\.open\b|object_hook' >/dev/null 2>&1; then
        add_finding "HIGH" "UNSAFE_PARSE" "Added code uses unsafe deserialization (eval, pickle, yaml.load, etc.)"
    fi
fi

# 14. Archive extraction / path traversal
echo "[14/14] Checking archive extraction & path traversal..."
if code_check; then
    if added_code | /usr/bin/grep -E '\btar\b[[:space:]]+-\S*x\S*|\btar\b[[:space:]]+--extract|\b(unzip|gunzip|bunzip2|cpio)\b[[:space:]]|\b7z\b[[:space:]]+x|\bar\b[[:space:]]+x|\bgzip[[:space:]]+-d\b|\bxz[[:space:]]+-d\b' >/dev/null 2>&1; then
        add_finding "MED" "ARCHIVE_EXTRACT" "Added code extracts archives (potential path traversal)"
    fi
fi
if added_code | /usr/bin/grep -E '(\.\./|\.\.\\|%2e%2e|%252e%252e).*\b(tar|unzip|cpio|ar|gunzip|bunzip2|7z)\b|\b(tar|unzip|cpio|ar|gunzip|bunzip2|7z)\b.*(\.\./|\.\.\\|%2e%2e|%252e%252e)' >/dev/null 2>&1; then
    add_finding "HIGH" "PATH_TRAVERSAL" "Added code combines path traversal patterns (../) with extraction or concatenated file access"
fi

# Injection patterns (SQL, command, template)
if code_check; then
    if added_code | /usr/bin/grep -E '\bsystem[[:space:]]*\(|\bpopen[[:space:]]*\(|\bsubprocess\.|\b(SELECT|INSERT|UPDATE|DELETE)\b.*\+|`[^`]*\$\(' >/dev/null 2>&1; then
        add_finding "HIGH" "INJECTION" "Added code contains potential injection patterns (SQL, command, template)"
    fi
fi

# Build recipe modification (PKGBUILD applying patches / changing sources)
if [[ "${HAS_PKGBUILD}" == "true" ]]; then
    if added_code | /usr/bin/grep -E '\bpatch\b[[:space:]]|source\+?=(\(|\[)|\bmakedepends\b|\bprepare[[:space:]]*\(' >/dev/null 2>&1; then
        add_finding "MED" "BUILD_RECIPE" "PKGBUILD build recipe modified (patch application or source changes — supply-chain surface)"
    fi
fi

# Additional: Check for new binary/executable files
echo "[Extra] Checking for new executables..."
if [[ -f "${FILES_FILE}" ]] && [[ -s "${FILES_FILE}" ]]; then
    while IFS= read -r line; do
        P=$(/usr/sbin/jq -r '.path // empty' <<< "${line}" 2>/dev/null || true)
        TYPE=$(/usr/sbin/jq -r '.changeType // empty' <<< "${line}" 2>/dev/null || true)
        [[ -z "${P}" || "${TYPE}" != "ADDED" ]] && continue
        if /usr/bin/grep -A5 -F "diff --git a/${P}" "${PATCH_FILE}" | /usr/bin/grep -q '^+#!'; then
            add_finding "MED" "NEW_EXECUTABLE" "New executable script added: ${P}"
        fi
    done < "${FILES_FILE}"
fi

# Check for large binary blobs
if /usr/bin/grep -q '^Binary files' "${PATCH_FILE}"; then
    add_finding "MED" "BINARY_BLOB" "Patch contains binary file changes (cannot inspect)"
fi

# Finalize
finalize_verdict

# Output report
REPORT_FILE="${PATCH_DIR}/security-scan.json"
/usr/bin/cat > "${REPORT_FILE}" <<EOF
{
  "patch_dir": "${PATCH_DIR}",
  "scanned_at": "$(/usr/bin/date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "verdict": "${VERDICT}",
  "classification": {
    "doc_only": ${DOC_ONLY},
    "has_code": ${HAS_CODE},
    "has_pkgbuild": ${HAS_PKGBUILD}
  },
  "risk_counts": {
    "high": ${HIGH_RISK},
    "medium": ${MED_RISK},
    "low": ${LOW_RISK}
  },
  "findings": $(printf '%s\n' "${REASONS[@]}" | /usr/sbin/jq -R . | /usr/sbin/jq -s .)
}
EOF

echo
echo "=== Security Scan Result ==="
echo "Verdict: ${VERDICT}"
echo "High: ${HIGH_RISK}  Medium: ${MED_RISK}  Low: ${LOW_RISK}"
echo
if [[ ${#REASONS[@]} -gt 0 ]]; then
    echo "Findings:"
    for r in "${REASONS[@]}"; do
        echo "  ${r}"
    done
else
    echo "No security findings."
fi
echo
echo "Report saved: ${REPORT_FILE}"

# Exit code based on verdict
case "${VERDICT}" in
    REJECTED) exit 2 ;;
    REQUIRES_SECURITY_REVIEW) exit 1 ;;
    *) exit 0 ;;
esac
