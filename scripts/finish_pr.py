#!/usr/bin/env python3
"""Complete PR lifecycle: merge, release claim, cleanup worktree.

Plan #189 Phase 5: Atomic Finish
This script validates ALL preconditions before taking ANY action,
ensuring either the PR merges completely or nothing happens.

MUST be run from main directory, not from a worktree. This prevents the
shell CWD invalidation issue where deleting a worktree breaks the CC's bash.

Usage:
    # From main directory:
    cd /path/to/main && python scripts/finish_pr.py --branch plan-XX --pr N

    # Or via make:
    cd /path/to/main && make finish BRANCH=plan-XX PR=N
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_cmd(
    cmd: list[str], check: bool = True, capture: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run a command, optionally capturing output."""
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
    )


def is_in_worktree() -> bool:
    """Check if current directory is a git worktree (not main repo)."""
    git_path = Path(".git")
    if git_path.is_file():
        # .git is a file pointing to the main repo = we're in a worktree
        return True
    elif git_path.is_dir():
        # .git is a directory = we're in the main repo
        return False
    else:
        # Not in a git repo at all
        return False


def get_main_repo_root() -> Path:
    """Get the main repo root directory."""
    result = run_cmd(["git", "rev-parse", "--git-common-dir"], check=False)
    if result.returncode != 0:
        return Path.cwd()
    git_common = Path(result.stdout.strip())
    return git_common.parent


def check_pr_ci_status(pr_number: int) -> tuple[bool, str]:
    """Check if PR's CI checks have passed."""
    result = run_cmd(
        ["gh", "pr", "view", str(pr_number), "--json", "statusCheckRollup,mergeable,state"],
        check=False,
    )
    if result.returncode != 0:
        return False, f"Failed to get PR status: {result.stderr}"

    data = json.loads(result.stdout)

    if data.get("state") == "MERGED":
        return False, "PR is already merged"

    if data.get("state") == "CLOSED":
        return False, "PR is closed"

    if data.get("mergeable") == "CONFLICTING":
        return False, "PR has merge conflicts - needs rebase"

    checks = data.get("statusCheckRollup", []) or []
    failing = [
        c.get("name", c.get("context", "unknown"))
        for c in checks
        if c.get("conclusion") == "FAILURE"
    ]
    if failing:
        return False, f"CI checks failing: {', '.join(failing)}"

    pending = [
        c.get("name", c.get("context", "unknown"))
        for c in checks
        if c.get("status") in ("IN_PROGRESS", "QUEUED", "PENDING")
        or c.get("conclusion") is None
    ]
    if pending:
        return False, f"CI checks still running: {', '.join(pending)}"

    return True, "OK"


def merge_pr(pr_number: int) -> tuple[bool, str]:
    """Merge a PR via GitHub CLI."""
    result = run_cmd(
        ["gh", "pr", "merge", str(pr_number), "--squash", "--delete-branch"],
        check=False,
    )
    if result.returncode != 0:
        return False, result.stderr or result.stdout
    return True, "Merged"


def release_claim(branch: str) -> bool:
    """Release any claim for this branch.

    Plan #176: With atomic claims (claim stored in worktree), the claim file
    is deleted when the worktree is removed. This just adds to completed history.
    We don't use --force since ownership should be verified.
    """
    result = run_cmd(
        ["python", "scripts/check_claims.py", "--release", "--id", branch],
        check=False,
    )
    return result.returncode == 0



def extract_plan_number(branch: str) -> str | None:
    """Extract plan number from branch name like 'plan-113-model-access'."""
    if not branch.startswith("plan-"):
        return None
    parts = branch.split("-")
    if len(parts) >= 2 and parts[1].isdigit():
        return parts[1]
    return None


def complete_plan(plan_number: str) -> tuple[bool, str]:
    """Mark a plan as complete using complete_plan.py."""
    result = run_cmd(
        ["python", "scripts/complete_plan.py", "--plan", plan_number],
        check=False,
    )
    if result.returncode != 0:
        return False, result.stderr or result.stdout or "Unknown error"
    return True, "Completed"

def find_worktree_path(branch: str) -> Path | None:
    """Find the worktree path for a branch."""
    result = run_cmd(["git", "worktree", "list", "--porcelain"], check=False)
    if result.returncode != 0:
        return None

    current_path = None
    for line in result.stdout.strip().split("\n"):
        if line.startswith("worktree "):
            current_path = Path(line[9:])
        elif line.startswith("branch refs/heads/"):
            worktree_branch = line[18:]
            if worktree_branch == branch:
                return current_path
    return None


def remove_worktree(worktree_path: Path) -> tuple[bool, str]:
    """Remove a worktree."""
    result = run_cmd(
        ["git", "worktree", "remove", str(worktree_path)],
        check=False,
    )
    if result.returncode != 0:
        # Try with --force for untracked files
        result = run_cmd(
            ["git", "worktree", "remove", "--force", str(worktree_path)],
            check=False,
        )
        if result.returncode != 0:
            return False, result.stderr or result.stdout
    return True, "Removed"


def check_worktree_clean(worktree_path: Path) -> tuple[bool, str]:
    """Check if worktree has uncommitted changes."""
    result = run_cmd(
        ["git", "-C", str(worktree_path), "status", "--porcelain"],
        check=False,
    )
    if result.returncode != 0:
        return True, ""  # Can't check, assume clean
    if result.stdout.strip():
        return False, result.stdout.strip()
    return True, ""


def check_worktree_processes(worktree_path: Path) -> list[dict[str, Any]]:
    """Check for processes using the worktree.

    Plan #189 Phase 5: Uses safe_worktree_remove's process check.
    """
    try:
        # Import here to avoid circular dependency
        from scripts.safe_worktree_remove import check_processes_using_worktree
        return check_processes_using_worktree(str(worktree_path))
    except ImportError:
        return []  # Graceful degradation


def validate_finish_preconditions(
    branch: str,
    pr_number: int,
    check_ci: bool = False,
) -> tuple[bool, list[str], dict[str, Any]]:
    """Validate all preconditions for finishing a PR.

    Plan #189 Phase 5: Atomic Finish
    This validates everything BEFORE any destructive operations.

    Returns:
        (all_ok, list_of_errors, context_dict)
        context_dict contains: worktree_path, plan_number, etc.
    """
    errors: list[str] = []
    context: dict[str, Any] = {
        "branch": branch,
        "pr_number": pr_number,
        "worktree_path": None,
        "plan_number": None,
    }

    # 1. Must be in main, not worktree
    if is_in_worktree():
        main_root = get_main_repo_root()
        errors.append(
            f"Must run from main, not worktree. Run: cd {main_root} && make finish ..."
        )
        return False, errors, context

    # 2. Check PR exists and is mergeable
    result = run_cmd(
        ["gh", "pr", "view", str(pr_number), "--json", "state,mergeable,headRefName"],
        check=False,
    )
    if result.returncode != 0:
        errors.append(f"PR #{pr_number} not found or cannot access")
    else:
        data = json.loads(result.stdout)
        if data.get("state") == "MERGED":
            errors.append(f"PR #{pr_number} is already merged")
        elif data.get("state") == "CLOSED":
            errors.append(f"PR #{pr_number} is closed")
        elif data.get("mergeable") == "CONFLICTING":
            errors.append(f"PR #{pr_number} has merge conflicts - needs rebase")

        # Verify branch matches PR
        pr_branch = data.get("headRefName")
        if pr_branch and pr_branch != branch:
            errors.append(
                f"Branch mismatch: PR is for '{pr_branch}', not '{branch}'"
            )

    # 3. Check CI if requested
    if check_ci:
        ci_ok, ci_msg = check_pr_ci_status(pr_number)
        if not ci_ok:
            errors.append(f"CI check: {ci_msg}")

    # 4. Check worktree state
    worktree_path = find_worktree_path(branch)
    context["worktree_path"] = worktree_path

    if worktree_path:
        # 4a. Check for uncommitted changes
        clean, changes = check_worktree_clean(worktree_path)
        if not clean:
            change_summary = changes.split("\n")[0][:50]
            errors.append(f"Worktree has uncommitted changes: {change_summary}...")

        # 4b. Check for processes using worktree (Plan #189 Phase 4)
        processes = check_worktree_processes(worktree_path)
        if processes:
            proc_names = [p.get("name", "?") for p in processes[:3]]
            errors.append(
                f"Worktree in use by {len(processes)} process(es): {', '.join(proc_names)}"
            )

    # 5. Extract plan number for context
    plan_num = extract_plan_number(branch)
    context["plan_number"] = plan_num

    return len(errors) == 0, errors, context


def finish_pr(branch: str, pr_number: int, check_ci: bool = False) -> bool:
    """Complete the full PR lifecycle.

    Plan #189 Phase 5: Atomic Finish
    Two-phase approach:
    1. VALIDATION PHASE - Check all preconditions, fail early if any issue
    2. EXECUTION PHASE - Only runs if all validations pass
    """
    print(f"🏁 Finishing PR #{pr_number} (branch: {branch})")
    print()

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 1: VALIDATION (can fail safely - no changes made yet)
    # ═══════════════════════════════════════════════════════════════════
    print("📋 Validating preconditions...")
    all_ok, errors, context = validate_finish_preconditions(branch, pr_number, check_ci)

    if not all_ok:
        print()
        print("❌ BLOCKED: Cannot finish PR")
        print("=" * 60)
        for error in errors:
            print(f"  • {error}")
        print("=" * 60)
        print()
        print("Fix these issues and retry.")
        return False

    print("✅ All preconditions validated")
    print()

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 2: EXECUTION (atomic - either completes fully or not at all)
    # ═══════════════════════════════════════════════════════════════════

    worktree_path = context.get("worktree_path")
    plan_num = context.get("plan_number")

    # Step 1: Remove worktree FIRST (before merge, so branch can be deleted)
    if worktree_path:
        print(f"🧹 Removing worktree at {worktree_path}...")
        # Remove session marker if present (we're the owner finishing our own work)
        session_marker = worktree_path / ".claude_session"
        if session_marker.exists():
            session_marker.unlink()
        remove_ok, remove_msg = remove_worktree(worktree_path)
        if remove_ok:
            print("✅ Worktree removed")
        else:
            # This shouldn't happen since we validated, but handle gracefully
            print(f"⚠️  Could not remove worktree: {remove_msg}")
            print(f"   Remove manually: git worktree remove --force {worktree_path}")
            print("   Then retry: make finish ...")
            return False

    # Step 2: Merge PR (now safe - branch not in use by worktree)
    # This is the only truly irreversible operation
    print(f"🔀 Merging PR #{pr_number}...")
    merge_ok, merge_msg = merge_pr(pr_number)
    if not merge_ok:
        print(f"❌ Merge failed: {merge_msg}")
        return False
    print("✅ PR merged")

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 3: CLEANUP (best-effort, logged - PR is already merged)
    # ═══════════════════════════════════════════════════════════════════

    # Step 3: Mark plan as complete (if this is a plan branch)
    if plan_num:
        print(f"📋 Marking Plan #{plan_num} as complete...")
        complete_ok, complete_msg = complete_plan(plan_num)
        if complete_ok:
            print(f"✅ Plan #{plan_num} marked complete")
        else:
            print(f"⚠️  Could not mark plan complete: {complete_msg}")
            print("   Run manually: python scripts/complete_plan.py --plan", plan_num)

    # Step 4: Release claim
    print(f"🔓 Releasing claim for {branch}...")
    if release_claim(branch):
        print("✅ Claim released")
    else:
        print("⚠️  No claim to release (or already released)")

    # Step 5: Pull main
    print("📥 Pulling latest main...")
    run_cmd(["git", "pull", "--rebase", "origin", "main"], check=False)
    print("✅ Main updated")

    print()
    print(f"🎉 Done! PR #{pr_number} is complete.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Complete PR lifecycle: merge, release claim, cleanup worktree.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--branch", "-b",
        required=True,
        help="Branch name (e.g., plan-98-robust-worktree)"
    )
    parser.add_argument(
        "--pr", "-p",
        type=int,
        required=True,
        help="PR number"
    )
    parser.add_argument(
        "--check-ci",
        action="store_true",
        help="Enable CI status check before merge (disabled by default)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate only, don't actually merge (Plan #189 Phase 5)"
    )

    args = parser.parse_args()

    if args.dry_run:
        print(f"🔍 Dry run: validating PR #{args.pr} (branch: {args.branch})")
        print()
        all_ok, errors, context = validate_finish_preconditions(
            args.branch, args.pr, args.check_ci
        )

        if all_ok:
            print("✅ All preconditions validated - PR can be finished")
            print()
            print("Would perform:")
            if context.get("worktree_path"):
                print(f"  1. Remove worktree: {context['worktree_path']}")
            print(f"  2. Merge PR #{args.pr}")
            if context.get("plan_number"):
                print(f"  3. Mark Plan #{context['plan_number']} complete")
            print(f"  4. Release claim for {args.branch}")
            print("  5. Pull latest main")
            return 0
        else:
            print("❌ Validation failed:")
            for error in errors:
                print(f"  • {error}")
            return 1

    success = finish_pr(args.branch, args.pr, args.check_ci)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
