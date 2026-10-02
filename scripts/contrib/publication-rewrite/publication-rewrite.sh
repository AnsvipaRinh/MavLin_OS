#!/usr/bin/env bash
# publication-rewrite.sh — prepare MavLinOS history for first public push.
#
# Rewrites history on a FRESH CLONE (never in-place) so that:
#   1. ALL commits carry the public identity
#      Ansvipa_Rinh <GITHUB_NOREPLY_EMAIL> (author AND committer);
#   2. personal name/email are neutralized in old doc-blob versions;
#   3. the archived Apple-derived originals (docs/isolated-assets/apple-derived/)
#      are removed from ALL history (user decision D1);
#   4. the 30 pre-522ab98 Apple-derived icon blobs are stripped
#      (the generic replacements at 522ab98+ survive untouched).
#
# Usage:
#   scripts/contrib/publication-rewrite.sh <GITHUB_NOREPLY_EMAIL> [source-repo]
#
#   <GITHUB_NOREPLY_EMAIL>  REQUIRED. The account's real noreply address,
#                           format <numeric-id>+Ansvipa_Rinh@users.noreply.github.com.
#                           Obtain it AFTER GitHub authentication:
#                             gh api user --jq '"\(.id)+\(.login)@users.noreply.github.com"'
#                           or GitHub Settings -> Emails. NEVER fabricate the
#                           numeric ID.
#   [source-repo]           defaults to the current directory's repo.
#
# Safety properties (all enforced, see verify_rewrite()):
#   * refuses to run if the source repo has ANY remote configured
#     (this procedure is for FIRST publication only — a repo that was
#     already pushed must NOT be rewritten this way);
#   * works only on a fresh clone; the source repo is never modified;
#   * after the rewrite, the HEAD tree must be BYTE-IDENTICAL to the
#     source HEAD tree (proof that no commit content changed beyond
#     the intended neutralizations);
#   * commit count must be preserved;
#   * exactly one author/committer identity must remain;
#   * the personal strings and the apple-derived path must be absent
#     from every remaining commit;
#   * all 30 target blob IDs must no longer exist;
#   * git fsck --full must be clean.
#
# The dry-run evidence for this procedure (executed 2026-10-03 with a
# TEST identity on a throwaway clone) is recorded in
# docs/FORENSIC_AUDIT.md §"Publication rewrite dry-run".

set -euo pipefail

NOREPLY_EMAIL="${1:-}"
SOURCE_REPO="${2:-.}"
WORKDIR="${TMPDIR:-/tmp}/mavlinos-publication-rewrite"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

die() { echo "FATAL: $*" >&2; exit 1; }

# --- input validation -------------------------------------------------------
[ -n "$NOREPLY_EMAIL" ] || die "usage: $0 <GITHUB_NOREPLY_EMAIL> [source-repo]

GITHUB_NOREPLY_EMAIL is REQUIRED and must be the account's real noreply
address (format: <numeric-id>+Ansvipa_Rinh@users.noreply.github.com).
Obtain it after GitHub authentication:
  gh api user --jq '\"\\(.id)+\\(.login)@users.noreply.github.com\"'
The numeric ID must NOT be fabricated."

case "$NOREPLY_EMAIL" in
  *"+Ansvipa_Rinh@users.noreply.github.com") ;;
  *) die "refusing: '$NOREPLY_EMAIL' does not look like the account noreply
address (expected pattern: <numeric-id>+Ansvipa_Rinh@users.noreply.github.com).
If your GitHub account uses a different noreply form, edit this check
deliberately — but the default guard exists to prevent publishing under
a made-up identity." ;;
esac

command -v git-filter-repo >/dev/null 2>&1 || \
  pip show git-filter-repo >/dev/null 2>&1 || \
  python3 -c "import git_filter_repo" 2>/dev/null || \
  die "git-filter-repo not found (install: pip install git-filter-repo)"

SOURCE_REPO="$(cd "$SOURCE_REPO" && pwd -P)"
git -C "$SOURCE_REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || die "not a git repository: $SOURCE_REPO"

# --- safety: source must be clean and REMOTE-FREE --------------------------
[ -z "$(git -C "$SOURCE_REPO" status --porcelain)" ] \
  || die "source repo has uncommitted changes — commit or stash first"
REMOTES="$(git -C "$SOURCE_REPO" remote)"
[ -z "$REMOTES" ] || die "source repo has remote(s): $REMOTES —
this procedure is for FIRST publication only. Rewriting a repo that was
already pushed would diverge from the published history. Aborting."

SRC_HEAD="$(git -C "$SOURCE_REPO" rev-parse HEAD)"
SRC_COMMITS="$(git -C "$SOURCE_REPO" rev-list --count HEAD)"
echo "source: $SOURCE_REPO"
echo "  HEAD:   $SRC_HEAD"
echo "  commits: $SRC_COMMITS"
echo "  remotes: (none) OK"

# --- fresh clone ------------------------------------------------------------
rm -rf "$WORKDIR"
git clone --no-local "$SOURCE_REPO" "$WORKDIR" >/dev/null
cd "$WORKDIR"

# --- build the real mailmap from the template + supplied email -------------
sed "s|<GITHUB_NOREPLY_EMAIL>|$NOREPLY_EMAIL|g" \
  "$SCRIPT_DIR/01-mailmap-template.txt" > .mailmap-rules.txt
# drop comment lines for filter-repo
grep -v '^#' .mailmap-rules.txt > .mailmap-clean.txt

echo "--- pass 1/4: mailmap (both identities -> Ansvipa_Rinh <$NOREPLY_EMAIL>)"
git filter-repo --mailmap .mailmap-clean.txt --force

echo "--- pass 2/4: replace-text (personal name/email in old doc blobs)"
git filter-repo --replace-text "$SCRIPT_DIR/02-replace-text.txt" --force

echo "--- pass 3/4: remove archived Apple-derived originals from ALL history"
git filter-repo --path docs/isolated-assets/apple-derived/ --invert-paths --force

echo "--- pass 4/4: strip 30 pre-522ab98 Apple-derived icon blobs"
git filter-repo --strip-blobs-with-id "$SCRIPT_DIR/03-apple-derived-blob-ids.txt" --force

# --- verification gates ------------------------------------------------------
verify_rewrite() {
  local fail=0

  NEW_COMMITS="$(git rev-list --count HEAD)"
  if [ "$NEW_COMMITS" = "$SRC_COMMITS" ]; then
    echo "  [OK] commit count preserved: $NEW_COMMITS"
  else
    echo "  [FAIL] commit count: $NEW_COMMITS != $SRC_COMMITS"; fail=1
  fi

  # exactly one author+committer identity, and it is the public one
  IDENTS="$(git log --format='%an <%ae>' | sort -u)"
  COMMITTERS="$(git log --format='%cn <%ce>' | sort -u)"
  if [ "$IDENTS" = "Ansvipa_Rinh <$NOREPLY_EMAIL>" ] \
     && [ "$COMMITTERS" = "Ansvipa_Rinh <$NOREPLY_EMAIL>" ]; then
    echo "  [OK] single author+committer identity: Ansvipa_Rinh <$NOREPLY_EMAIL>"
  else
    echo "  [FAIL] identities: authors={$IDENTS} committers={$COMMITTERS}"; fail=1
  fi

  # personal strings absent from every remaining commit's content
  if git log --all -p | grep -qE "Vsevolod|vsevolod@archlinux|Avdonkin"; then
    echo "  [FAIL] personal identity strings still present in history"; fail=1
  else
    echo "  [OK] personal name/email absent from all history content"
  fi

  # apple-derived archived path absent from all history
  if git log --all --name-only --format= | grep -q "isolated-assets/apple-derived"; then
    echo "  [FAIL] apple-derived archived path still in history"; fail=1
  else
    echo "  [OK] docs/isolated-assets/apple-derived absent from all history"
  fi

  # all 30 target blob IDs must no longer exist
  local missing=0 present=0
  while read -r blob; do
    case "$blob" in \#*) continue;; esac
    [ -z "$blob" ] && continue
    if git cat-file -e "$blob" 2>/dev/null; then present=$((present+1)); else missing=$((missing+1)); fi
  done < "$SCRIPT_DIR/03-apple-derived-blob-ids.txt"
  if [ "$present" -eq 0 ] && [ "$missing" -eq 30 ]; then
    echo "  [OK] all 30 Apple-derived blobs stripped (0 remain)"
  else
    echo "  [FAIL] blob strip: $present still present, $missing stripped (want 0/30)"; fail=1
  fi

  # HEAD tree byte-identical to source HEAD tree (content unchanged beyond intent)
  SRC_TREE="$(git -C "$SOURCE_REPO" rev-parse "$SRC_HEAD^{tree}")"
  NEW_TREE="$(git rev-parse HEAD^{tree})"
  if [ "$SRC_TREE" = "$NEW_TREE" ]; then
    echo "  [OK] HEAD tree identical to source ($SRC_TREE)"
  else
    echo "  [FAIL] HEAD tree changed: $SRC_TREE -> $NEW_TREE"; fail=1
  fi

  if git fsck --full >/dev/null 2>&1; then
    echo "  [OK] git fsck --full clean"
  else
    echo "  [FAIL] git fsck reported problems"; fail=1
  fi

  return $fail
}

echo "--- verification"
if verify_rewrite; then
  echo
  echo "REWRITE VERIFIED. Rewritten repo: $WORKDIR"
  echo "Next steps (manual, authenticated):"
  echo "  git -C $WORKDIR branch -M main        # if not already main"
  echo "  git -C $WORKDIR remote add origin https://github.com/Ansvipa_Rinh/MavLinOS.git"
  echo "  git -C $WORKDIR push -u origin main"
  echo "  git -C $SOURCE_REPO remote add origin https://github.com/Ansvipa_Rinh/MavLinOS.git"
  echo "  # then replace the local repo with the rewritten copy, or push from the copy"
else
  echo
  echo "VERIFICATION FAILED — do NOT push $WORKDIR. Inspect with:"
  echo "  cd $WORKDIR && git log --format='%an <%ae>' | sort -u"
  exit 1
fi
