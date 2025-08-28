#!/usr/bin/env bash
set -euo pipefail

# merge dev into main and keep dev branch
# Usage: scripts/deploy_website.sh [remote]
# Env overrides: DEV_BRANCH, MAIN_BRANCH

remote="${1:-origin}"
DEV_BRANCH="${DEV_BRANCH:-dev}"
MAIN_BRANCH="${MAIN_BRANCH:-main}"

info() {
  printf "[INFO] %s\n" "$*"
}

error() {
  printf "[ERROR] %s\n" "$*" >&2
}

require_clean_worktree() {
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    error "Not inside a git repository"
    exit 1
  fi

  if [ -n "$(git status --porcelain)" ]; then
    error "Working tree is not clean. Commit, stash, or discard changes first."
    git status --short
    exit 1
  fi
}

ensure_branch_exists() {
  local branch="$1"
  if git show-ref --verify --quiet "refs/heads/${branch}"; then
    return 0
  fi
  if git show-ref --verify --quiet "refs/remotes/${remote}/${branch}"; then
    return 0
  fi
  error "Branch '${branch}' not found locally or on remote '${remote}'."
  exit 1
}

current_branch="$(git symbolic-ref --short HEAD 2>/dev/null || echo "DETACHED")"

restore_branch() {
  local target="$1"
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    if [ -n "$target" ] && [ "$target" != "$(git symbolic-ref --short HEAD 2>/dev/null || echo "DETACHED")" ]; then
      git checkout -q "$target" || true
    fi
  fi
}

on_error() {
  error "Deployment failed. Restoring branch '${current_branch}'."
  restore_branch "$current_branch"
}
trap on_error ERR INT

require_clean_worktree

info "Fetching from remote '${remote}'"
git fetch "$remote" --prune

ensure_branch_exists "$DEV_BRANCH"
ensure_branch_exists "$MAIN_BRANCH"

info "Checking out '${DEV_BRANCH}' and updating"
git checkout "$DEV_BRANCH"
git pull --ff-only "$remote" "$DEV_BRANCH"

info "Checking out '${MAIN_BRANCH}' and updating"
git checkout "$MAIN_BRANCH"
git pull --ff-only "$remote" "$MAIN_BRANCH"

info "Merging '${DEV_BRANCH}' into '${MAIN_BRANCH}'"
git merge --no-ff --no-edit "$DEV_BRANCH"

info "Pushing '${MAIN_BRANCH}' to '${remote}'"
git push "$remote" "$MAIN_BRANCH"

info "Restoring original branch '${current_branch}'"
restore_branch "$current_branch"

info "Done. '${MAIN_BRANCH}' now includes '${DEV_BRANCH}'."
exit 0


