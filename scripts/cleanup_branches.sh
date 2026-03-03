#!/usr/bin/env bash
# SPDX-License-Identifier: MIT OR LicenseRef-Commercial
#
# cleanup_branches.sh — Delete remote branches that have already been merged into master.
#
# Usage:
#   ./scripts/cleanup_branches.sh          # interactive (asks before deleting)
#   ./scripts/cleanup_branches.sh --dry-run # list branches that would be deleted
#   ./scripts/cleanup_branches.sh --yes     # delete without prompting

set -euo pipefail

MAIN_BRANCH="master"
DRY_RUN=false
AUTO_YES=false

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --yes|-y)  AUTO_YES=true ;;
    --help|-h)
      echo "Usage: $0 [--dry-run] [--yes]"
      echo "  --dry-run  List merged branches without deleting them"
      echo "  --yes      Delete without prompting for confirmation"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
  esac
done

# Fetch latest remote state
echo "Fetching latest remote branch info..."
git fetch --prune origin

# Get current branch so we never delete it
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")

# List remote branches merged into origin/master, excluding master itself
MERGED_BRANCHES=$(git branch -r --merged "origin/$MAIN_BRANCH" \
  | grep -v "origin/$MAIN_BRANCH" \
  | grep -v "origin/HEAD" \
  | sed 's|origin/||' \
  | sed 's/^[[:space:]]*//' \
  || true)

if [ -z "$MERGED_BRANCHES" ]; then
  echo "No merged remote branches to clean up. Only '$MAIN_BRANCH' remains."
  exit 0
fi

echo ""
echo "The following remote branches have been merged into '$MAIN_BRANCH':"
echo "-------------------------------------------------------------------"
for branch in $MERGED_BRANCHES; do
  if [ "$branch" = "$CURRENT_BRANCH" ]; then
    echo "  $branch  (current branch — will skip)"
  else
    echo "  $branch"
  fi
done
echo ""

if $DRY_RUN; then
  echo "(Dry run — no branches were deleted)"
  exit 0
fi

if ! $AUTO_YES; then
  read -rp "Delete these remote branches? [y/N] " confirm
  if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
  fi
fi

for branch in $MERGED_BRANCHES; do
  if [ "$branch" = "$CURRENT_BRANCH" ]; then
    echo "Skipping '$branch' (current branch)"
    continue
  fi
  echo "Deleting origin/$branch ..."
  git push origin --delete "$branch" && echo "  ✓ Deleted" || echo "  ✗ Failed"
done

# Clean up local tracking refs
git fetch --prune origin

echo ""
echo "Done. Remaining remote branches:"
git branch -r | grep -v "origin/HEAD" | sed 's/^/  /'
