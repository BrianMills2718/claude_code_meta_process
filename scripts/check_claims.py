#!/usr/bin/env python3
"""Check for stale claims and manage active work.

Usage:
    # Check for stale claims (default: >4 hours old)
    python scripts/check_claims.py

    # List all claims
    python scripts/check_claims.py --list

    # List available features
    python scripts/check_claims.py --list-features

    # Claim a feature (recommended)
    python scripts/check_claims.py --claim --feature ledger --task "Fix transfer bug"

    # Claim a plan
    python scripts/check_claims.py --claim --plan 3 --task "Docker isolation"

    # Claim both feature and plan
    python scripts/check_claims.py --claim --feature escrow --plan 8 --task "Agent rights"

    # Check if files are covered by claims (CI mode)
    python scripts/check_claims.py --check-files src/world/ledger.py src/world/executor.py

    # Release current branch's claim
    python scripts/check_claims.py --release

    # Verify current branch has a claim (CI mode)
    python scripts/check_claims.py --verify-claim

    # Verify a specific branch has a claim (for pre-push hook)
    python scripts/check_claims.py --verify-branch my-branch

    # Clean up old completed entries (>24h)
    python scripts/check_claims.py --cleanup

Branch name is used as instance identity by default.
Primary data store: .claude/active-work.yaml

Scope-Based Claims:
    Claims should specify a scope (--plan and/or --feature).
    - Plans are defined in docs/plans/*.md
    - Features are defined in meta/acceptance_gates/*.yaml
    Each scope can only be claimed by one instance at a time.
    Use --force to override (NOT recommended).

Special Cases:
    - "shared" feature: Files in meta/acceptance_gates/shared.yaml have NO claim conflicts.
      These are cross-cutting files (config, fixtures) any plan can modify.
    - [Trivial] commits: Don't require claims. See CI workflow for validation.
"""

import argparse
import os
import re
import socket
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml


# Session identity configuration
STALENESS_MINUTES = 30  # Sessions with no activity for this long are considered stale
SESSION_DIR_NAME = "sessions"

# Atomic claim file - stored in each worktree
CLAIM_FILE_NAME = ".claim.yaml"


def get_main_repo_root() -> Path:
    """Get the main repo root (not worktree).

    For worktrees, returns the main repository's root directory.
    This ensures claims are stored in a shared location.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=True,
        )
        git_dir = Path(result.stdout.strip())
        # git-common-dir returns the .git directory, so parent is repo root
        return git_dir.parent
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


# Use main repo root for claims to share across worktrees
_MAIN_ROOT = get_main_repo_root()
YAML_PATH = _MAIN_ROOT / ".claude/active-work.yaml"
CLAUDE_MD_PATH = _MAIN_ROOT / "CLAUDE.md"
PLANS_DIR = _MAIN_ROOT / "docs/plans"


def get_git_toplevel() -> Path:
    """Get the current git working tree root (works for both main and worktrees)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


# Use current git toplevel for features (branch-specific)
FEATURES_DIR = get_git_toplevel() / "meta/acceptance_gates"

# Session directory for session identity tracking
SESSIONS_DIR = _MAIN_ROOT / ".claude" / SESSION_DIR_NAME


def get_session_file_name() -> str:
    """Generate session file name based on hostname and PID."""
    hostname = socket.gethostname()
    pid = os.getpid()
    return f"{hostname}-{pid}.session"


def get_session_file_path() -> Path:
    """Get the full path to this process's session file."""
    return SESSIONS_DIR / get_session_file_name()


def load_session(session_file: Path) -> dict[str, Any] | None:
    """Load a session from file."""
    if not session_file.exists():
        return None
    try:
        with open(session_file) as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return None


def save_session(session_file: Path, data: dict[str, Any]) -> None:
    """Save session data to file."""
    session_file.parent.mkdir(parents=True, exist_ok=True)
    with open(session_file, "w") as f:
        yaml.dump(data, f, default_flow_style=False)


def get_or_create_session() -> dict[str, Any]:
    """Get existing session or create a new one.

    Returns the session data dict with:
    - session_id: UUID string
    - hostname: Machine hostname
    - pid: Process ID
    - started_at: ISO timestamp
    - last_activity: ISO timestamp
    """
    session_file = get_session_file_path()
    session = load_session(session_file)

    if session and session.get("session_id"):
        # Update last_activity
        session["last_activity"] = datetime.now(timezone.utc).isoformat()
        save_session(session_file, session)
        return session

    # Create new session
    now = datetime.now(timezone.utc).isoformat()
    session = {
        "session_id": str(uuid.uuid4()),
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "started_at": now,
        "last_activity": now,
        "working_on": None,
    }
    save_session(session_file, session)
    return session


def get_session_id() -> str:
    """Get the session ID for the current process, creating if needed."""
    session = get_or_create_session()
    return session["session_id"]


def is_session_stale(
    session_id: str,
    staleness_minutes: int = STALENESS_MINUTES,
) -> tuple[bool, dict[str, Any] | None]:
    """Check if a session is stale (no activity for N minutes).

    Args:
        session_id: The session ID to check
        staleness_minutes: Minutes of inactivity before considered stale

    Returns:
        (is_stale, session_data) - session_data is None if session not found
    """
    if not SESSIONS_DIR.exists():
        return True, None

    # Find session file by session_id
    for session_file in SESSIONS_DIR.glob("*.session"):
        session = load_session(session_file)
        if session and session.get("session_id") == session_id:
            last_activity = session.get("last_activity")
            if not last_activity:
                return True, session

            try:
                last_time = datetime.fromisoformat(last_activity)
                # Ensure timezone aware
                if last_time.tzinfo is None:
                    last_time = last_time.replace(tzinfo=timezone.utc)

                now = datetime.now(timezone.utc)
                age = now - last_time

                if age > timedelta(minutes=staleness_minutes):
                    return True, session
                return False, session
            except ValueError:
                return True, session

    # Session not found
    return True, None


def update_session_heartbeat(working_on: str | None = None) -> dict[str, Any]:
    """Update the session's last_activity timestamp.

    Args:
        working_on: Optional description of current work (e.g., "Plan #134")

    Returns:
        Updated session data
    """
    session_file = get_session_file_path()
    session = load_session(session_file)

    if not session:
        session = get_or_create_session()
    else:
        session["last_activity"] = datetime.now(timezone.utc).isoformat()
        if working_on is not None:
            session["working_on"] = working_on
        save_session(session_file, session)

    return session


def load_all_features() -> dict[str, dict[str, Any]]:
    """Load all feature definitions from meta/acceptance_gates/*.yaml.

    Returns dict mapping feature name to feature data.
    """
    features: dict[str, dict[str, Any]] = {}

    if not FEATURES_DIR.exists():
        return features

    for path in list(FEATURES_DIR.glob("*.yaml")) + list(FEATURES_DIR.glob("*.yml")):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
                if data and "feature" in data:
                    features[data["feature"]] = data
        except (yaml.YAMLError, FileNotFoundError):
            continue

    return features


def get_feature_names() -> list[str]:
    """Get list of valid feature names."""
    features = load_all_features()
    return sorted(features.keys())


def build_file_to_feature_map() -> dict[str, str]:
    """Build mapping from file paths to feature names.

    Uses the 'code:' section in each feature definition.
    """
    file_map: dict[str, str] = {}
    features = load_all_features()

    for feature_name, data in features.items():
        code_files = data.get("code", [])
        for filepath in code_files:
            # Normalize path
            normalized = str(Path(filepath))
            file_map[normalized] = feature_name

    return file_map


def check_scope_conflict(
    new_plan: int | None,
    new_feature: str | None,
    existing_claims: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Check if new claim conflicts with existing claims.

    Conflicts occur when:
    - Same plan number is claimed
    - Same feature is claimed

    Exception: The "shared" feature never conflicts. Multiple plans can
    modify shared files (config, fixtures) simultaneously. Tests are
    the quality gate, not claim exclusivity.

    Returns list of conflicting claims.
    """
    conflicts: list[dict[str, Any]] = []

    # Shared feature never conflicts - anyone can modify shared files
    if new_feature == "shared":
        return []

    for claim in existing_claims:
        existing_plan = claim.get("plan")
        existing_feature = claim.get("feature")

        # Exact plan match
        if new_plan and existing_plan and new_plan == existing_plan:
            conflicts.append(claim)
            continue

        # Exact feature match (but not for shared)
        if new_feature and existing_feature and new_feature == existing_feature:
            if existing_feature != "shared":  # Shared never conflicts
                conflicts.append(claim)
                continue

    return conflicts


def check_files_claimed(
    modified_files: list[str],
    claims: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    """Check if modified files are covered by claims.

    Returns (claimed_files, unclaimed_files).

    Note: Files in the "shared" feature are always considered claimed.
    This allows any plan to modify cross-cutting infrastructure files
    (config, fixtures, etc.) without needing to explicitly claim them.
    """
    file_map = build_file_to_feature_map()

    # Get all claimed features and plans
    claimed_features: set[str] = set()
    claimed_plans: set[int] = set()

    for claim in claims:
        if claim.get("feature"):
            claimed_features.add(claim["feature"])
        if claim.get("plan"):
            claimed_plans.add(claim["plan"])

    claimed: list[str] = []
    unclaimed: list[str] = []

    for filepath in modified_files:
        normalized = str(Path(filepath))
        feature = file_map.get(normalized)

        # Shared files are always considered claimed (no conflicts)
        if feature == "shared":
            claimed.append(filepath)
        elif feature and feature in claimed_features:
            claimed.append(filepath)
        else:
            # File is not in any feature's code section, or feature not claimed
            unclaimed.append(filepath)

    return claimed, unclaimed


def get_plan_status(plan_number: int) -> tuple[str, list[int]]:
    """Get plan status and its blockers.

    Returns (status, blocked_by_list).
    Status is one of: 'complete', 'in_progress', 'blocked', 'planned', 'needs_plan', 'unknown'
    """
    plan_file = None
    for f in PLANS_DIR.glob(f"{plan_number:02d}_*.md"):
        plan_file = f
        break
    if not plan_file:
        for f in PLANS_DIR.glob(f"{plan_number}_*.md"):
            plan_file = f
            break

    if not plan_file or not plan_file.exists():
        return ("unknown", [])

    content = plan_file.read_text()

    # Parse status
    status = "unknown"
    status_match = re.search(r"\*\*Status:\*\*\s*(.+)", content)
    if status_match:
        raw_status = status_match.group(1).strip().lower()
        if "✅" in raw_status or "complete" in raw_status:
            status = "complete"
        elif "🚧" in raw_status or "in progress" in raw_status:
            status = "in_progress"
        elif "⏸️" in raw_status or "blocked" in raw_status:
            status = "blocked"
        elif "📋" in raw_status or "planned" in raw_status:
            status = "planned"
        elif "❌" in raw_status or "needs plan" in raw_status:
            status = "needs_plan"

    # Parse blockers
    blockers: list[int] = []
    blocked_match = re.search(r"\*\*Blocked By:\*\*\s*(.+)", content)
    if blocked_match:
        blocked_raw = blocked_match.group(1).strip()
        # Extract numbers from patterns like "#1", "#2, #3", "None"
        blocker_numbers = re.findall(r"#(\d+)", blocked_raw)
        blockers = [int(n) for n in blocker_numbers]

    return (status, blockers)


def check_plan_dependencies(plan_number: int) -> tuple[bool, list[str]]:
    """Check if all dependencies for a plan are complete.

    Returns (all_ok, list_of_issues).
    """
    status, blockers = get_plan_status(plan_number)
    issues: list[str] = []

    if not blockers:
        return (True, [])

    for blocker in blockers:
        blocker_status, _ = get_plan_status(blocker)
        if blocker_status != "complete":
            issues.append(f"Plan #{blocker} is not complete (status: {blocker_status})")

    return (len(issues) == 0, issues)


def cleanup_old_completed(data: dict[str, Any], hours: int = 24) -> int:
    """Remove completed entries older than threshold.

    Returns number of entries removed.
    """
    now = datetime.now(timezone.utc)
    threshold = timedelta(hours=hours)

    completed = data.get("completed", [])
    original_count = len(completed)

    # Keep only recent completions
    data["completed"] = [
        c for c in completed
        if (ts := parse_timestamp(c.get("completed_at", ""))) is None
        or (now - ts) <= threshold
    ]

    removed = original_count - len(data["completed"])
    if removed > 0:
        save_yaml(data)

    return removed


def cleanup_merged_claims(data: dict[str, Any]) -> tuple[int, list[str]]:
    """Auto-cleanup claims for branches that have been merged to main.

    This is Phase 3 of Plan #189 - branch-based claims.
    When a branch is merged to main, its claim should be automatically released.

    Returns (count_cleaned, list_of_worktrees_to_remove).
    """
    merged_branches = get_merged_branches()
    if not merged_branches:
        return 0, []

    claims = data.get("claims", [])
    worktrees_to_remove: list[str] = []
    cleaned_count = 0

    claims_to_keep: list[dict[str, Any]] = []

    for claim in claims:
        cc_id = claim.get("cc_id", "")
        if cc_id in merged_branches:
            # Branch is merged - move claim to completed
            completion = {
                "cc_id": cc_id,
                "plan": claim.get("plan"),
                "task": claim.get("task"),
                "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "auto_completed": True,
                "reason": "branch_merged",
            }
            data["completed"].append(completion)
            cleaned_count += 1

            # Track worktree for removal suggestion
            wt_path = claim.get("worktree_path")
            if wt_path:
                worktrees_to_remove.append(wt_path)
        else:
            claims_to_keep.append(claim)

    if cleaned_count > 0:
        data["claims"] = claims_to_keep
        # Keep only last 50 completions
        data["completed"] = data["completed"][-50:]
        save_yaml(data)

    return cleaned_count, worktrees_to_remove


def get_current_branch() -> str:
    """Get current git branch name."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"



def branch_exists_on_remote(branch: str) -> bool:
    """Check if a branch exists on the remote origin.

    Returns True if branch exists, False if deleted/merged.
    """
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", branch],
            capture_output=True,
            text=True,
            check=True,
            cwd=_MAIN_ROOT,
        )
        # If output is non-empty, branch exists
        return bool(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Can't check remote, assume branch exists
        return True


def get_merged_branches() -> set[str]:
    """Get set of branches that have been merged to main.

    Returns branch names (without refs/heads/ prefix).
    """
    merged: set[str] = set()
    try:
        # Get branches merged to main
        result = subprocess.run(
            ["git", "branch", "-r", "--merged", "origin/main"],
            capture_output=True,
            text=True,
            check=True,
            cwd=_MAIN_ROOT,
        )
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line.startswith("origin/") and line != "origin/main":
                branch = line.replace("origin/", "")
                merged.add(branch)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return merged


def get_worktrees() -> list[dict[str, Any]]:
    """Get git worktree information with recent activity."""
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            cwd=_MAIN_ROOT,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    worktrees: list[dict[str, Any]] = []
    current: dict[str, Any] = {}

    for line in result.stdout.strip().split("\n"):
        if line.startswith("worktree "):
            if current:
                worktrees.append(current)
            current = {"path": line[9:]}
        elif line.startswith("HEAD "):
            current["commit"] = line[5:]
        elif line.startswith("branch "):
            current["branch"] = line[7:].replace("refs/heads/", "")
        elif line == "detached":
            current["branch"] = "(detached)"

    if current:
        worktrees.append(current)

    for wt in worktrees:
        if wt.get("commit"):
            try:
                result = subprocess.run(
                    ["git", "log", "-1", "--format=%ct", wt["commit"]],
                    capture_output=True,
                    text=True,
                    check=True,
                    cwd=_MAIN_ROOT,
                )
                timestamp = int(result.stdout.strip())
                wt["last_commit_time"] = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            except (subprocess.CalledProcessError, ValueError):
                wt["last_commit_time"] = None

    return worktrees


def load_claim_from_worktree(worktree_path: str) -> dict[str, Any] | None:
    """Load claim from a worktree's .claim.yaml file.

    Returns the claim dict or None if no claim file exists.
    """
    claim_file = Path(worktree_path) / CLAIM_FILE_NAME
    if not claim_file.exists():
        return None

    try:
        with open(claim_file) as f:
            claim = yaml.safe_load(f)
            if claim:
                # Add worktree_path for reference
                claim["worktree_path"] = worktree_path
                return claim
    except (yaml.YAMLError, OSError):
        pass
    return None


def save_claim_to_worktree(
    worktree_path: str,
    cc_id: str,
    task: str,
    plan: int | None = None,
    feature: str | None = None,
    session_id: str | None = None,
) -> bool:
    """Save claim to a worktree's .claim.yaml file.

    This is the atomic claim - worktree exists = claim exists.
    """
    if session_id is None:
        session_id = get_session_id()

    claim_data: dict[str, Any] = {
        "cc_id": cc_id,
        "task": task,
        "claimed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session_id": session_id,
    }

    if plan:
        claim_data["plan"] = plan
    if feature:
        claim_data["feature"] = feature

    claim_file = Path(worktree_path) / CLAIM_FILE_NAME
    try:
        with open(claim_file, "w") as f:
            f.write("# Atomic claim file - this worktree is claimed\n")
            f.write("# Deleting worktree = releasing claim\n\n")
            yaml.dump(claim_data, f, default_flow_style=False, sort_keys=False)
        return True
    except OSError as e:
        print(f"Error writing claim file: {e}")
        return False


def load_claims_from_worktrees() -> list[dict[str, Any]]:
    """Load all claims from worktree .claim.yaml files.

    This is the primary source of truth for active claims.
    Scans all worktrees and reads their claim files.
    """
    claims: list[dict[str, Any]] = []
    worktrees = get_worktrees()

    for wt in worktrees:
        path = wt.get("path", "")
        branch = wt.get("branch", "")

        # Skip main repo (not a worktree for work)
        if branch == "main":
            continue

        claim = load_claim_from_worktree(path)
        if claim:
            # Ensure cc_id matches branch
            claim["cc_id"] = branch
            claims.append(claim)

    return claims


def find_worktree_for_branch(branch: str) -> str | None:
    """Find the worktree path for a given branch."""
    worktrees = get_worktrees()
    for wt in worktrees:
        if wt.get("branch") == branch:
            return wt.get("path")
    return None


def get_worktree_claim_status(
    worktrees: list[dict[str, Any]],
    claims: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Cross-reference worktrees with claims."""
    branch_to_claim: dict[str, dict[str, Any]] = {}
    for claim in claims:
        cc_id = claim.get("cc_id", "")
        branch_to_claim[cc_id] = claim

    # Get merged branches for status display
    merged_branches = get_merged_branches()

    results: list[dict[str, Any]] = []

    for wt in worktrees:
        branch = wt.get("branch", "")
        path = wt.get("path", "")

        if path.endswith("/agent_ecology") and "worktrees" not in path:
            continue

        wt_claim = branch_to_claim.get(branch)
        is_merged = branch in merged_branches

        if is_merged:
            status = "MERGED"
        elif wt_claim:
            status = "claimed"
        else:
            last_commit = wt.get("last_commit_time")
            if last_commit:
                hours_ago = (datetime.now(timezone.utc) - last_commit).total_seconds() / 3600
                if hours_ago < 4:
                    status = "ACTIVE_NO_CLAIM"
                else:
                    status = "orphaned"
            else:
                status = "orphaned"

        results.append({
            **wt,
            "claim": wt_claim,
            "status": status,
            "is_merged": is_merged,
        })

    return results


def verify_has_claim(data: dict[str, Any], branch: str) -> tuple[bool, str]:
    """Verify the current branch has an active claim.

    Returns (has_claim, message).
    """
    claims = data.get("claims", [])

    # Check if this branch has a claim
    for claim in claims:
        if claim.get("cc_id") == branch:
            task = claim.get("task", "")
            return (True, f"Active claim: {task}")

    # Special case: main branch with no active PRs is allowed for reviews
    if branch == "main":
        return (False, "No claim on main branch (use worktree for implementation)")

    return (False, f"No active claim for branch '{branch}'")


def load_yaml() -> dict[str, Any]:
    """Load claims from worktrees (primary) and YAML file (fallback/completed).

    Active claims are read from worktree .claim.yaml files.
    The YAML file is used for:
    - completed history
    - backwards compatibility during migration (claims without worktrees)
    """
    # Load completed history from YAML
    completed: list[dict[str, Any]] = []
    legacy_claims: list[dict[str, Any]] = []

    if YAML_PATH.exists():
        with open(YAML_PATH) as f:
            data = yaml.safe_load(f) or {}
        completed = data.get("completed") or []
        legacy_claims = data.get("claims") or []

    # Load active claims from worktrees (primary source of truth)
    worktree_claims = load_claims_from_worktrees()

    # Merge: worktree claims take precedence, add legacy claims that don't have worktrees
    worktree_branches = {c.get("cc_id") for c in worktree_claims}
    for legacy in legacy_claims:
        if legacy.get("cc_id") not in worktree_branches:
            # Legacy claim without worktree - keep for backwards compat
            legacy["_legacy"] = True
            worktree_claims.append(legacy)

    return {
        "claims": worktree_claims,
        "completed": completed,
    }


def save_yaml(data: dict[str, Any]) -> None:
    """Save claims to YAML file."""
    YAML_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(YAML_PATH, "w") as f:
        f.write("# Active Work Lock File\n")
        f.write("# Machine-readable tracking for multi-CC coordination.\n")
        f.write("# Use: python scripts/check_claims.py --help\n\n")
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def parse_timestamp(ts: str) -> datetime | None:
    """Parse various timestamp formats.

    All timestamps are assumed to be UTC. Returns timezone-aware datetime.
    """
    if not ts:
        return None

    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            # Parse and attach UTC timezone (timestamps in YAML are UTC)
            dt = datetime.strptime(ts.strip(), fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def get_age_string(ts: datetime) -> str:
    """Get human-readable age string."""
    now = datetime.now(timezone.utc)
    hours = (now - ts).total_seconds() / 3600

    if hours < 1:
        return f"{int(hours * 60)}m ago"
    elif hours < 24:
        return f"{hours:.1f}h ago"
    else:
        return f"{hours / 24:.1f}d ago"


def check_stale_claims(claims: list[dict], hours: int) -> list[dict]:
    """Return claims older than the threshold."""
    now = datetime.now(timezone.utc)
    threshold = timedelta(hours=hours)
    stale = []

    for claim in claims:
        ts = parse_timestamp(claim.get("claimed_at", ""))
        if ts and (now - ts) > threshold:
            claim["age_hours"] = (now - ts).total_seconds() / 3600
            stale.append(claim)

    return stale


# =============================================================================
# Plan #206: Enhanced Stale Claim Detection and Cleanup
# =============================================================================


def get_worktree_last_modified(worktree_path: str) -> datetime | None:
    """Get the most recent modification time of any file in the worktree.

    This is used to determine if a claim is stale based on actual activity,
    not just when the claim was created.

    Args:
        worktree_path: Path to the worktree directory

    Returns:
        datetime of most recent modification, or None if path doesn't exist
    """
    path = Path(worktree_path)
    if not path.exists() or not path.is_dir():
        return None

    most_recent: datetime | None = None

    # Check common activity indicators
    # 1. Git index (changes when staging/committing)
    git_index = path / ".git" / "index"
    if not git_index.exists():
        # For worktrees, .git is a file pointing to the actual git dir
        git_file = path / ".git"
        if git_file.is_file():
            # Try to get the actual git dir
            try:
                content = git_file.read_text().strip()
                if content.startswith("gitdir:"):
                    actual_git = Path(content[7:].strip())
                    git_index = actual_git / "index"
            except (OSError, ValueError):
                pass

    if git_index.exists():
        try:
            mtime = datetime.fromtimestamp(git_index.stat().st_mtime, tz=timezone.utc)
            if most_recent is None or mtime > most_recent:
                most_recent = mtime
        except OSError:
            pass

    # 2. Check recently modified source files (but not too deep to avoid slowness)
    source_dirs = ["src", "scripts", "tests", "docs"]
    checked_files = 0
    max_files = 100  # Limit to avoid slowness on large repos

    for src_dir in source_dirs:
        src_path = path / src_dir
        if not src_path.exists():
            continue

        for file_path in src_path.rglob("*"):
            if checked_files >= max_files:
                break
            if file_path.is_file() and not file_path.name.startswith("."):
                try:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
                    if most_recent is None or mtime > most_recent:
                        most_recent = mtime
                    checked_files += 1
                except OSError:
                    pass

    # 3. Fallback: check the worktree root itself
    if most_recent is None:
        try:
            most_recent = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            pass

    return most_recent


def is_claim_stale(
    claim: dict[str, Any],
    max_hours: int = 8,
) -> tuple[bool, str]:
    """Check if a claim is stale based on worktree activity.

    A claim is stale if:
    - The worktree path doesn't exist
    - The worktree has no activity for max_hours

    Args:
        claim: Claim dict with at least 'cc_id' and optionally 'worktree_path'
        max_hours: Hours of inactivity before claim is considered stale

    Returns:
        (is_stale, reason) tuple
    """
    worktree_path = claim.get("worktree_path")

    # No worktree path = definitely stale
    if not worktree_path:
        return True, "No worktree path in claim"

    # Worktree doesn't exist = stale
    if not Path(worktree_path).exists():
        return True, f"Worktree does not exist: {worktree_path}"

    # Check last modification time
    last_modified = get_worktree_last_modified(worktree_path)
    if last_modified is None:
        return True, "Could not determine worktree activity"

    now = datetime.now(timezone.utc)
    hours_since = (now - last_modified).total_seconds() / 3600

    if hours_since > max_hours:
        return True, f"Worktree inactive for {hours_since:.1f}h (threshold: {max_hours}h)"

    return False, f"Active {hours_since:.1f}h ago"


def cleanup_stale_claims(
    claims: list[dict[str, Any]],
    max_hours: int = 8,
    dry_run: bool = False,
) -> list[str]:
    """Find and optionally release stale claims.

    A claim is stale if:
    - Its worktree doesn't exist
    - Its worktree has no activity for max_hours

    Args:
        claims: List of claim dicts
        max_hours: Hours of inactivity before claim is considered stale
        dry_run: If True, just report what would be cleaned up

    Returns:
        List of cc_ids that were (or would be) released
    """
    released: list[str] = []

    for claim in claims:
        cc_id = claim.get("cc_id", "unknown")
        is_stale, reason = is_claim_stale(claim, max_hours)

        if is_stale:
            released.append(cc_id)
            if not dry_run:
                # The actual release would happen here, but for now
                # we just report - the caller handles the release
                pass

    return released


def is_valid_worktree_location(
    worktree_path: str,
    repo_root: str,
) -> tuple[bool, str]:
    """Check if a worktree is in the standard location.

    Worktrees should be in {repo_root}/worktrees/ to ensure proper tracking.

    Args:
        worktree_path: Path to the worktree
        repo_root: Path to the main repository root

    Returns:
        (is_valid, reason) tuple
    """
    expected_prefix = str(Path(repo_root) / "worktrees") + "/"
    worktree_str = str(Path(worktree_path))

    if worktree_str.startswith(expected_prefix):
        return True, "Standard location"

    return False, f"Expected worktree in {expected_prefix}, got: {worktree_str}"


def cleanup_orphaned_claims(
    claims: list[dict[str, Any]],
    dry_run: bool = False,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Remove claims where the worktree no longer exists.

    This is a more aggressive cleanup than cleanup_stale_claims -
    it removes claims immediately if the worktree is gone, regardless
    of how old the claim is.

    Args:
        claims: List of claim dicts
        dry_run: If True, just report what would be cleaned up

    Returns:
        (cleaned_cc_ids, remaining_claims) tuple
    """
    cleaned: list[str] = []
    remaining: list[dict[str, Any]] = []

    for claim in claims:
        cc_id = claim.get("cc_id", "unknown")
        worktree_path = claim.get("worktree_path")

        # No worktree path or worktree doesn't exist = orphaned
        if not worktree_path or not Path(worktree_path).exists():
            cleaned.append(cc_id)
        else:
            remaining.append(claim)

    return cleaned, remaining


def list_claims(claims: list[dict], show_worktrees: bool = True) -> None:
    """Print claims AND worktrees with cross-referencing.

    Shows both to prevent confusion about active work.
    """
    worktrees = get_worktrees() if show_worktrees else []
    wt_status = get_worktree_claim_status(worktrees, claims) if worktrees else []
    wt_branches = {wt.get("branch", "") for wt in wt_status}

    # Check for merged branches (Phase 3: branch-based claims)
    merged_branches = get_merged_branches()
    
    if not claims:
        print("No active claims.")
    else:
        print("Active Claims:")
        print("-" * 70)

        for claim in claims:
            ts = parse_timestamp(claim.get("claimed_at", ""))
            age = get_age_string(ts) if ts else "unknown"

            cc_id = claim.get("cc_id", "?")
            plan = claim.get("plan")
            feature = claim.get("feature")
            task = claim.get("task", "")[:35]

            scope_parts = []
            if plan:
                scope_parts.append(f"Plan #{plan}")
            if feature:
                scope_parts.append(f"'{feature}'")
            scope_str = " + ".join(scope_parts) if scope_parts else "unscoped"
            
            has_wt = cc_id in wt_branches
            is_merged = cc_id in merged_branches

            indicators = []
            if not has_wt:
                indicators.append("NO WORKTREE")
            if is_merged:
                indicators.append("MERGED")
            indicator_str = f" [{', '.join(indicators)}]" if indicators else ""

            print(f"  {cc_id:15} | {scope_str:20} | {task:30} | {age}{indicator_str}")
            if claim.get("files"):
                print(f"                   Files: {', '.join(claim['files'][:3])}")
    
    if wt_status:
        print()
        print("Worktrees:")
        print("-" * 70)
        
        active_no_claim = []
        
        merged_worktrees = []
        for wt in wt_status:
            branch = wt.get("branch", "?")
            status = wt.get("status", "?")
            last_commit = wt.get("last_commit_time")

            age = get_age_string(last_commit) if last_commit else "unknown"

            if status == "MERGED":
                status_str = "!! MERGED (cleanup needed)"
                merged_worktrees.append(wt)
            elif status == "ACTIVE_NO_CLAIM":
                status_str = "!! ACTIVE (no claim)"
                active_no_claim.append(wt)
            elif status == "claimed":
                claim = wt.get("claim", {})
                plan = claim.get("plan")
                status_str = f"Claimed (Plan #{plan})" if plan else "Claimed"
            else:
                status_str = "orphaned"

            print(f"  {branch:30} | {status_str:25} | last: {age}")
        
        if active_no_claim:
            print()
            print("=" * 70)
            print("!! WARNING: ACTIVE WORKTREES WITHOUT CLAIMS")
            print("=" * 70)
            print("Another CC instance may be working in these worktrees!")
            for wt in active_no_claim:
                print(f"  - {wt.get('branch', '?')}: {wt.get('path', '?')}")
            print("=" * 70)

        if merged_worktrees:
            print()
            print("=" * 70)
            print("!! MERGED BRANCHES - CLEANUP AVAILABLE")
            print("=" * 70)
            print("These branches have been merged to main. Clean up with:")
            print()
            print("  python scripts/check_claims.py --cleanup-merged")
            print()
            print("Or remove worktrees manually:")
            for wt in merged_worktrees:
                branch = wt.get("branch", "?")
                print(f"  make worktree-remove BRANCH={branch}")
            print("=" * 70)


def add_claim(
    data: dict[str, Any],
    cc_id: str,
    plan: int | None,
    feature: str | None,
    task: str,
    files: list[str] | None = None,
    worktree_path: str | None = None,
    force: bool = False,
    session_id: str | None = None,
) -> bool:
    """Add a new claim.

    Args:
        data: Claims data structure
        cc_id: Instance identifier (usually branch name)
        plan: Plan number to claim (optional)
        feature: Feature name to claim (optional)
        task: Task description
        files: Specific files being worked on (optional)
        worktree_path: Path to worktree (for session tracking, Plan #52)
        force: Force claim despite conflicts
        session_id: Session ID for ownership verification (Plan #134)

    Plan #176: Claims are now stored in worktree .claim.yaml files.
    The worktree IS the claim - no orphaned claims possible.
    """
    # Plan #176: Block claiming on main branch - must use worktree
    if cc_id == "main":
        print("=" * 60)
        print("ERROR: Cannot claim on main branch")
        print("=" * 60)
        print()
        print("Implementation work must happen in a worktree.")
        print("Use: make worktree")
        print()
        print("This creates a worktree AND claims the work atomically.")
        return False

    # Check for existing claim by this instance
    for claim in data["claims"]:
        if claim.get("cc_id") == cc_id:
            existing_task = claim.get("task", "unknown")
            print(f"Error: {cc_id} already has an active claim: {existing_task}")
            print("Release it first with: python scripts/check_claims.py --release")
            return False

    # Check plan dependencies (if plan specified)
    if plan:
        deps_ok, dep_issues = check_plan_dependencies(plan)
        if not deps_ok:
            print(f"DEPENDENCY CHECK FAILED for Plan #{plan}:")
            for issue in dep_issues:
                print(f"  - {issue}")
            if not force:
                print("\nUse --force to claim anyway (not recommended).")
                return False
            print("\n--force specified, proceeding despite dependency issues.\n")

    # Validate feature name if provided
    if feature:
        valid_features = get_feature_names()
        if feature not in valid_features:
            print(f"Error: Unknown feature '{feature}'")
            print(f"Valid features: {', '.join(valid_features)}")
            return False

    # Check for scope conflicts (exact match on plan or feature)
    conflicts = check_scope_conflict(plan, feature, data["claims"])
    if conflicts:
        print("=" * 60)
        print("❌ SCOPE CONFLICT - CLAIM BLOCKED")
        print("=" * 60)
        for conflict in conflicts:
            existing_cc = conflict.get("cc_id", "?")
            existing_plan = conflict.get("plan")
            existing_feature = conflict.get("feature")
            existing_task = conflict.get("task", "")[:50]

            if existing_plan and plan and existing_plan == plan:
                print(f"\n  Plan #{plan} already claimed by: {existing_cc}")
            if existing_feature and feature and existing_feature == feature:
                print(f"\n  Feature '{feature}' already claimed by: {existing_cc}")
            print(f"  Their task: {existing_task}")

        print("\n" + "-" * 60)
        print("Each plan/feature can only be claimed by one instance.")
        print("Coordinate with the other instance before proceeding.")

        if not force:
            print("\nUse --force to claim anyway (NOT recommended).")
            return False
        print("\n--force specified, proceeding despite conflict.\n")

    # Get session ID if not provided (Plan #134: Session Identity)
    if session_id is None:
        session_id = get_session_id()

    new_claim: dict[str, Any] = {
        "cc_id": cc_id,
        "task": task,
        "claimed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session_id": session_id,
    }

    if plan:
        new_claim["plan"] = plan
    if feature:
        new_claim["feature"] = feature
    if files:
        new_claim["files"] = files
    if worktree_path:
        new_claim["worktree_path"] = worktree_path

    # Plan #176: Write claim to worktree if it exists
    wt_path = worktree_path or find_worktree_for_branch(cc_id)
    if wt_path:
        # Atomic claim: write to worktree
        if save_claim_to_worktree(wt_path, cc_id, task, plan, feature, session_id):
            new_claim["worktree_path"] = wt_path
        else:
            print(f"Warning: Could not write claim to worktree at {wt_path}")

    # Also save to YAML for backwards compatibility during migration
    data["claims"].append(new_claim)
    save_yaml(data)

    # Build output message
    scope_parts = []
    if plan:
        scope_parts.append(f"Plan #{plan}")
    if feature:
        scope_parts.append(f"Feature '{feature}'")
    scope_str = " + ".join(scope_parts) if scope_parts else "unscoped"

    print(f"Claimed: {cc_id} -> {scope_str}: {task}")
    return True


def validate_plan_for_completion(plan_number: int) -> tuple[bool, list[str]]:
    """Run TDD and other validation checks for a plan.

    Returns (passed, list_of_issues).
    """
    issues: list[str] = []

    # Check required tests pass
    result = subprocess.run(
        ["python", "scripts/check_plan_tests.py", "--plan", str(plan_number)],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        if "MISSING" in result.stdout:
            missing_count = result.stdout.count("[MISSING]")
            issues.append(f"{missing_count} required test(s) missing")
        elif "No test requirements defined" not in result.stdout:
            issues.append("Required tests failing")

    # Check full test suite
    result = subprocess.run(
        ["pytest", "tests/", "-q", "--tb=no"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        match = re.search(r"(\d+) failed", result.stdout)
        fail_count = match.group(1) if match else "some"
        issues.append(f"Test suite: {fail_count} test(s) failing")

    return (len(issues) == 0, issues)


def release_claim(
    data: dict[str, Any],
    cc_id: str,
    commit: str | None = None,
    validate: bool = False,
    force: bool = False,
    session_id: str | None = None,
) -> bool:
    """Release a claim and move to completed.

    Args:
        data: Claims data structure
        cc_id: Instance identifier to release
        commit: Optional commit hash to record
        validate: Run TDD validation before release
        force: Force release despite ownership or validation failures
        session_id: Session ID for ownership verification (Plan #134)
    """
    claim_to_remove = None

    for claim in data["claims"]:
        if claim.get("cc_id") == cc_id:
            claim_to_remove = claim
            break

    if not claim_to_remove:
        print(f"No active claim found for {cc_id}")
        return False

    # Ownership verification (Plan #134: Session Identity)
    # Only the session that created the claim can release it
    claim_session = claim_to_remove.get("session_id")
    if claim_session and not force:
        # Get current session ID if not provided
        if session_id is None:
            session_id = get_session_id()

        if claim_session != session_id:
            # Check if the owning session is stale
            is_stale, stale_session = is_session_stale(claim_session)

            if is_stale:
                print(f"Note: Claim owner session is stale, allowing takeover")
            else:
                print("=" * 60)
                print("❌ OWNERSHIP VERIFICATION FAILED")
                print("=" * 60)
                print(f"\nClaim owned by session: {claim_session[:8]}...")
                print(f"Your session:           {session_id[:8]}...")
                print("\nYou can only release claims you own.")
                print("\nIf the owner session is gone, wait for it to become stale")
                print(f"(no activity for {STALENESS_MINUTES} minutes) or use --force.")
                print("\nUse --force to release anyway (NOT recommended).")
                return False

    # Run validation if requested
    plan = claim_to_remove.get("plan")
    if validate and plan:
        print(f"Validating Plan #{plan} before release...")
        valid, issues = validate_plan_for_completion(plan)
        if not valid:
            print("VALIDATION FAILED:")
            for issue in issues:
                print(f"  - {issue}")
            if not force:
                print("\nUse --force to release anyway (not recommended).")
                return False
            print("\n--force specified, releasing despite validation failures.\n")
    elif plan and not validate:
        print(f"Tip: Use --validate to check TDD requirements before release.")

    data["claims"].remove(claim_to_remove)

    # Add to completed history
    completion = {
        "cc_id": cc_id,
        "plan": claim_to_remove.get("plan"),
        "task": claim_to_remove.get("task"),
        "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if commit:
        completion["commit"] = commit

    data["completed"].append(completion)

    # Keep only last 20 completions
    data["completed"] = data["completed"][-20:]

    save_yaml(data)
    print(f"Released: {cc_id} (Plan #{claim_to_remove.get('plan')})")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manage active work claims for multi-CC coordination",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--hours", "-H",
        type=int,
        default=4,
        help="Hours before a claim is considered stale (default: 4)"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all active claims"
    )
    parser.add_argument(
        "--claim",
        action="store_true",
        help="Claim work (uses current branch as ID)"
    )
    parser.add_argument(
        "--id",
        help="Explicit instance ID (default: current branch)"
    )
    parser.add_argument(
        "--plan", "-p",
        type=int,
        help="Plan number (optional)"
    )
    parser.add_argument(
        "--task", "-t",
        help="Task description"
    )
    parser.add_argument(
        "--release", "-r",
        action="store_true",
        help="Release current branch's claim"
    )
    parser.add_argument(
        "--commit",
        help="Commit hash when releasing (optional)"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove completed entries older than 24h"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force claim even if dependencies not met"
    )
    parser.add_argument(
        "--check-deps",
        type=int,
        metavar="PLAN",
        help="Check dependencies for a plan (without claiming)"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run TDD validation when releasing (recommended for plan claims)"
    )
    parser.add_argument(
        "--verify-claim",
        action="store_true",
        help="CI mode: verify current branch has an active claim (exit 1 if not)"
    )
    parser.add_argument(
        "--feature", "-F",
        type=str,
        help="Feature name to claim (from meta/acceptance_gates/*.yaml)"
    )
    parser.add_argument(
        "--list-features",
        action="store_true",
        help="List all available feature names"
    )
    parser.add_argument(
        "--check-files",
        type=str,
        nargs="+",
        metavar="FILE",
        help="Check if files are covered by current claims"
    )
    parser.add_argument(
        "--verify-branch",
        type=str,
        metavar="BRANCH",
        help="CI mode: verify a specific branch has an active claim (exit 1 if not)"
    )
    parser.add_argument(
        "--check-plan-session",
        type=int,
        metavar="PLAN",
        help="Check if plan is claimable (unclaimed or owned by this session). Exit 0=ok, 1=blocked"
    )
    parser.add_argument(
        "--get-session-id",
        action="store_true",
        help="Print current session ID"
    )
    parser.add_argument(
        "--heartbeat",
        action="store_true",
        help="Update session heartbeat (call periodically to prevent staleness)"
    )
    parser.add_argument(
        "--working-on",
        type=str,
        help="Description of current work (used with --heartbeat)"
    )
    parser.add_argument(
        "--check-conflict",
        action="store_true",
        help="Check if plan/feature would conflict (exit 0=ok, 1=conflict). Does NOT create claim."
    )
    parser.add_argument(
        "--write-claim-file",
        type=str,
        metavar="WORKTREE_PATH",
        help="Write .claim.yaml to specified worktree path (used by create_worktree.sh)"
    )
    parser.add_argument(
        "--cleanup-merged",
        action="store_true",
        help="Auto-cleanup claims for branches that have been merged to main"
    )
    parser.add_argument(
        "--cleanup-orphaned",
        action="store_true",
        help="Remove claims where worktree no longer exists (Plan #206)"
    )
    parser.add_argument(
        "--cleanup-stale",
        action="store_true",
        help="Release claims with no worktree activity for --stale-hours (Plan #206)"
    )
    parser.add_argument(
        "--stale-hours",
        type=int,
        default=8,
        help="Hours of inactivity before a claim is considered stale (default: 8)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be cleaned up without making changes"
    )

    args = parser.parse_args()

    data = load_yaml()
    claims = data.get("claims", [])

    # Determine instance ID (explicit or from branch)
    instance_id = args.id or get_current_branch()

    # Handle get-session-id (Plan #134)
    if args.get_session_id:
        session_id = get_session_id()
        print(session_id)
        return 0

    # Handle heartbeat (Plan #134)
    if args.heartbeat:
        session = update_session_heartbeat(args.working_on)
        print(f"Heartbeat updated for session {session['session_id'][:8]}...")
        return 0

    # Handle check-conflict (Plan #176: Check without creating claim)
    if args.check_conflict:
        plan = args.plan
        feature = args.feature

        if not plan and not feature:
            print("Error: --check-conflict requires --plan or --feature")
            return 1

        conflicts = check_scope_conflict(plan, feature, claims)
        if conflicts:
            print("CONFLICT: Scope already claimed")
            for conflict in conflicts:
                cc_id = conflict.get("cc_id", "?")
                task = conflict.get("task", "")[:50]
                print(f"  {cc_id}: {task}")
            return 1
        else:
            print("OK: No conflicts")
            return 0

    # Handle write-claim-file (Plan #176: Write claim to worktree)
    if args.write_claim_file:
        worktree_path = args.write_claim_file
        task = args.task
        plan = args.plan
        feature = args.feature

        if not task:
            print("Error: --write-claim-file requires --task")
            return 1

        # Check for conflicts first
        conflicts = check_scope_conflict(plan, feature, claims)
        if conflicts and not args.force:
            print("CONFLICT: Cannot write claim, scope already claimed")
            for conflict in conflicts:
                cc_id = conflict.get("cc_id", "?")
                print(f"  {cc_id}")
            return 1

        # Write the claim file
        cc_id = instance_id
        if save_claim_to_worktree(worktree_path, cc_id, task, plan, feature):
            print(f"Claim file written to {worktree_path}/{CLAIM_FILE_NAME}")
            return 0
        else:
            print(f"Error: Failed to write claim file")
            return 1

    # Handle check-plan-session (Plan #134)
    # Used by protect-main.sh to check if a plan can be edited by this session
    if args.check_plan_session:
        plan_num = args.check_plan_session
        my_session = get_session_id()

        # Find claim for this plan
        plan_claim = None
        for claim in claims:
            if claim.get("plan") == plan_num:
                plan_claim = claim
                break

        if not plan_claim:
            # Plan not claimed - ok to edit
            print(f"Plan #{plan_num}: unclaimed, ok to edit")
            return 0

        claim_session = plan_claim.get("session_id")
        if not claim_session:
            # Legacy claim without session ID - allow (backwards compat)
            print(f"Plan #{plan_num}: legacy claim (no session), ok to edit")
            return 0

        if claim_session == my_session:
            # We own this claim
            print(f"Plan #{plan_num}: owned by this session, ok to edit")
            return 0

        # Check if owner session is stale
        stale, _ = is_session_stale(claim_session)
        if stale:
            print(f"Plan #{plan_num}: owner session stale, ok to take over")
            return 0

        # Blocked - another active session owns this
        print(f"Plan #{plan_num}: blocked - owned by active session {claim_session[:8]}...")
        return 1

    # Handle check-deps
    if args.check_deps:
        deps_ok, issues = check_plan_dependencies(args.check_deps)
        if deps_ok:
            print(f"Plan #{args.check_deps}: All dependencies satisfied ✓")
            return 0
        else:
            print(f"Plan #{args.check_deps}: Dependencies NOT satisfied:")
            for issue in issues:
                print(f"  - {issue}")
            return 1

    # Handle verify-claim (CI mode)
    if args.verify_claim:
        has_claim, message = verify_has_claim(data, instance_id)
        if has_claim:
            print(f"✓ {message}")
            return 0
        else:
            print("=" * 60)
            print("❌ CLAIM VERIFICATION FAILED")
            print("=" * 60)
            print(f"\n{message}")
            print("\nAll implementation work requires an active claim.")
            print("This ensures coordination between Claude instances.")
            print("\nTo fix:")
            print("  1. Create a worktree: make worktree BRANCH=my-feature")
            print("  2. Claim work: python scripts/check_claims.py --claim --task 'My task'")
            print("  3. Then commit your changes")
            return 1

    # Handle verify-branch (CI mode - for pre-push hook)
    if args.verify_branch:
        branch = args.verify_branch
        has_claim, message = verify_has_claim(data, branch)
        if has_claim:
            print(f"✓ {message}")
            return 0
        else:
            # Silent failure - used by pre-push hook which shows its own message
            return 1

    # Handle list-features
    if args.list_features:
        features = get_feature_names()
        if not features:
            print("No features defined in meta/acceptance_gates/*.yaml")
            return 0
        print("Available features:")
        for f in features:
            print(f"  - {f}")

        # Show file mapping
        file_map = build_file_to_feature_map()
        if file_map:
            print(f"\nFiles mapped to features: {len(file_map)}")
        return 0

    # Handle check-files (CI mode)
    if args.check_files:
        claimed, unclaimed = check_files_claimed(args.check_files, claims)
        if unclaimed:
            print("❌ Files not covered by claims:")
            for f in unclaimed:
                print(f"  - {f}")

            print("\nTo fix, claim the feature that owns these files:")
            file_map = build_file_to_feature_map()
            suggested_features: set[str] = set()
            for f in unclaimed:
                feature = file_map.get(str(Path(f)))
                if feature:
                    suggested_features.add(feature)
            if suggested_features:
                print(f"  python scripts/check_claims.py --claim --feature {list(suggested_features)[0]} --task '...'")
            return 1
        else:
            print(f"✓ All {len(claimed)} file(s) covered by claims")
            return 0

    # Handle cleanup
    if args.cleanup:
        removed = cleanup_old_completed(data)
        if removed > 0:
            print(f"Cleaned up {removed} completed entries older than 24h")
        else:
            print("No old completed entries to clean up")
        return 0

    # Handle cleanup-merged (Phase 3: branch-based claims)
    if args.cleanup_merged:
        cleaned, worktrees = cleanup_merged_claims(data)
        if cleaned > 0:
            print(f"Auto-completed {cleaned} claim(s) for merged branches")
            if worktrees:
                print("\nWorktrees that can be removed:")
                for wt in worktrees:
                    print(f"  make worktree-remove BRANCH={Path(wt).name}")
        else:
            print("No claims found for merged branches")
        return 0

    # Handle cleanup-orphaned (Plan #206)
    if args.cleanup_orphaned:
        cleaned_ids, remaining = cleanup_orphaned_claims(claims, dry_run=args.dry_run)
        if cleaned_ids:
            action = "Would remove" if args.dry_run else "Removed"
            print(f"{action} {len(cleaned_ids)} orphaned claim(s):")
            for cc_id in cleaned_ids:
                print(f"  - {cc_id}")

            if not args.dry_run:
                # Update the data structure
                data["claims"] = remaining
                # Move cleaned to completed
                for cc_id in cleaned_ids:
                    completion = {
                        "cc_id": cc_id,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "reason": "auto_released_orphaned",
                    }
                    data["completed"].append(completion)
                # Keep only last 50 completions
                data["completed"] = data["completed"][-50:]
                save_yaml(data)
        else:
            print("No orphaned claims found")
        return 0

    # Handle cleanup-stale (Plan #206)
    if args.cleanup_stale:
        stale_ids = cleanup_stale_claims(claims, max_hours=args.stale_hours, dry_run=True)
        if stale_ids:
            action = "Would release" if args.dry_run else "Released"
            print(f"{action} {len(stale_ids)} stale claim(s) (>{args.stale_hours}h inactive):")
            for cc_id in stale_ids:
                # Find the claim to show more info
                claim = next((c for c in claims if c.get("cc_id") == cc_id), None)
                if claim:
                    _, reason = is_claim_stale(claim, args.stale_hours)
                    print(f"  - {cc_id}: {reason}")
                else:
                    print(f"  - {cc_id}")

            if not args.dry_run:
                # Remove stale claims from data
                remaining = [c for c in claims if c.get("cc_id") not in stale_ids]
                data["claims"] = remaining
                # Move to completed
                for cc_id in stale_ids:
                    claim = next((c for c in claims if c.get("cc_id") == cc_id), {})
                    completion = {
                        "cc_id": cc_id,
                        "plan": claim.get("plan"),
                        "task": claim.get("task"),
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "reason": "auto_released_stale",
                    }
                    data["completed"].append(completion)
                data["completed"] = data["completed"][-50:]
                save_yaml(data)
        else:
            print(f"No stale claims found (threshold: {args.stale_hours}h)")
        return 0

    # Handle claim
    if args.claim:
        if not args.task:
            print("Error: --claim requires --task")
            print("Example: python scripts/check_claims.py --claim --feature ledger --task 'Fix transfer bug'")
            return 1
        if not args.plan and not args.feature:
            print("Warning: No --plan or --feature specified. Consider scoping your claim.")
            print("  Use --plan N for plan-based work")
            print("  Use --feature NAME for feature-based work")
            print("  Use --list-features to see available features")
        if instance_id == "main":
            print("Warning: Claiming on 'main' branch. Consider using a feature branch.")
        success = add_claim(data, instance_id, args.plan, args.feature, args.task, force=args.force)
        return 0 if success else 1

    # Handle release
    if args.release:
        success = release_claim(
            data, instance_id, args.commit,
            validate=args.validate, force=args.force
        )
        return 0 if success else 1

    # Handle list
    if args.list:
        list_claims(claims)
        return 0

    # Default: check for stale claims
    stale = check_stale_claims(claims, args.hours)

    if not claims:
        print("No active claims.")
        return 0

    if not stale:
        print(f"No stale claims (threshold: {args.hours}h)")
        list_claims(claims)
        return 0

    print(f"STALE CLAIMS (>{args.hours}h old):")
    print("-" * 60)
    for claim in stale:
        print(f"  {claim.get('cc_id', '?'):8} | Plan #{claim.get('plan', '?'):<3} | {claim.get('age_hours', 0):.1f}h old")
        print(f"           Task: {claim.get('task', '')}")

    print()
    print("To release a stale claim:")
    print("  python scripts/check_claims.py --release <CC_ID>")

    return 1


if __name__ == "__main__":
    sys.exit(main())
