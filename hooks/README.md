# Hooks Overview

This directory contains hook templates for the meta-process framework. There are two types of hooks:

1. **Git Hooks** - Run on git operations (commit, push)
2. **Claude Code Hooks** - Run on Claude Code tool operations (Edit, Write, Bash, Read)

## Quick Reference

### Git Hooks (`hooks/`)

| Hook | Trigger | Purpose | Blocking |
|------|---------|---------|----------|
| `pre-commit` | Before commit | Doc-coupling, mypy, config validation, branch freshness | Yes |
| `commit-msg` | After message entered | Validates `[Plan #N]` or `[Trivial]` prefix | Yes |
| `post-commit` | After commit | Reminds about unpushed commits | No (warning) |
| `pre-push` | Before push | Warns if no active claim for branch | No (warning) |

### Claude Code Hooks (`.claude/hooks/`)

| Hook | Trigger | Purpose | Blocking |
|------|---------|---------|----------|
| `protect-main.sh` | Edit/Write | Block edits in main directory | Yes |
| `block-worktree-remove.sh` | Bash | Block direct `git worktree` commands | Yes |
| `check-cwd-valid.sh` | Bash | Fail gracefully if CWD was deleted | Yes |
| `protect-uncommitted.sh` | Bash | Block destructive git commands with uncommitted changes | Yes |
| `enforce-make-merge.sh` | Bash | Block direct `gh pr merge`, enforce `make merge` | Yes |
| `check-file-scope.sh` | Edit/Write | Block edits to files not in plan's scope | Yes (optional) |
| `check-inbox.sh` | Edit/Write | Block edits if unread messages exist | Yes (optional) |
| `check-references-reviewed.sh` | Edit/Write | Warn if plan lacks References Reviewed | No (warning) |
| `inject-governance-context.sh` | Read | Add ADR context after reading governed files | No (info) |
| `notify-inbox-startup.sh` | Read/Glob | Warn about unread messages once on startup | No (warning) |
| `warn-worktree-cwd.sh` | Session start | Warn if running from inside a worktree | No (warning) |
| `session-startup-cleanup.sh` | Session start | Auto-cleanup orphaned claims | No (cleanup) |
| `refresh-session-marker.sh` | Edit/Write | Update session marker for worktree tracking | No (tracking) |
| `check-hook-enabled.sh` | (helper) | Check if a hook is enabled in config | N/A |
| `check-planning-patterns.sh` | Edit/Write (plans) | Validate planning patterns in plan files | Configurable |
| `pre-commit-planning-patterns.sh` | pre-commit | Validate planning patterns before commit | Configurable |

## Exit Codes

All hooks use consistent exit codes:

| Code | Meaning |
|------|---------|
| 0 | Success / Allow operation |
| 1 | Block operation (with error message) |
| 2 | Block operation (permission/validation issue) |

## Debugging Hooks

### Enable Debug Output

```bash
# Set DEBUG=1 to see detailed hook output
DEBUG=1 git commit -m "[Trivial] Test"

# For Claude Code hooks
DEBUG=1 claude
```

### Test Hooks Manually

```bash
# Git hooks
./hooks/pre-commit
./hooks/commit-msg .git/COMMIT_EDITMSG

# Claude Code hooks (simulate tool call)
./.claude/hooks/protect-main.sh /path/to/file.py
```

### Check Hook Configuration

```bash
# See which hooks are enabled
cat meta-process.yaml | grep -A 20 "hooks:"

# Check if specific hook is enabled
source .claude/hooks/check-hook-enabled.sh
is_hook_enabled "check_file_scope" && echo "enabled"
```

## Enabling/Disabling Hooks

### Git Hooks

Git hooks are controlled by the `core.hooksPath` config:

```bash
# Enable (point to hooks directory)
git config core.hooksPath hooks

# Disable (use default, which has no hooks)
git config --unset core.hooksPath

# Bypass for single commit
git commit --no-verify -m "..."
```

### Claude Code Hooks

Claude Code hooks are configured in `meta-process.yaml`:

```yaml
hooks:
  # Core hooks (always recommended)
  protect_main: true
  block_worktree_remove: true
  check_cwd_valid: true

  # Optional hooks
  check_file_scope: false      # Requires plan with Files Affected
  check_inbox: false           # Requires inter-CC messaging enabled
  check_references_reviewed: true
```

Or disable all hooks by removing the `.claude/hooks/` directory.

## Hook Details

### protect-main.sh

**Purpose:** Prevent editing files directly in main directory.

**Why:** Multiple Claude Code instances share main. Edits here can conflict or be overwritten. Forces use of worktrees for isolation.

**Blocked:**
- Edit/Write to any file in main (not in a worktree)
- Edit/Write to worktrees without an active claim

**Allowed:**
- Edit/Write to files in claimed worktrees

**Recovery:**
```bash
# Create a worktree first
make worktree
# Then edit in worktrees/your-branch/
```

### block-worktree-remove.sh

**Purpose:** Prevent bypassing the claim system.

**Blocked:**
- `git worktree add` (use `make worktree` instead)
- `git worktree remove` (use `make worktree-remove` instead)

**Why:** Direct git worktree commands bypass claiming, breaking coordination.

### check-file-scope.sh

**Purpose:** Keep work focused on declared scope.

**Blocked:** Edit/Write to files not listed in plan's `## Files Affected` section.

**Recovery:**
```markdown
## Files Affected
- src/module.py          <!-- Add files you need to edit -->
- tests/test_module.py
```

### enforce-make-merge.sh

**Purpose:** Ensure PRs go through proper validation.

**Blocked:**
- `gh pr merge` (use `make merge PR=N` instead)
- `python scripts/merge_pr.py` directly

**Why:** `make merge` runs validation checks before merging.

### inject-governance-context.sh

**Purpose:** Show relevant ADRs when reading governed files.

**Behavior:** After Read tool completes on a governed file, injects a reminder about which ADRs apply.

**Not blocking:** Just informational.

## Installation

### For New Projects

```bash
./meta-process/install.sh /path/to/project --minimal
```

This copies hooks and configures git.

### Manual Setup

```bash
# Git hooks
git config core.hooksPath hooks

# Claude Code hooks (create settings.json)
mkdir -p .claude
cat > .claude/settings.json << 'EOF'
{
  "hooks": {
    "PreToolUse": [
      {"matcher": {"tool_name": "Edit"}, "hooks": [{"type": "command", "command": "bash .claude/hooks/protect-main.sh \"$TOOL_INPUT_FILE_PATH\""}]}
    ]
  }
}
EOF
```

## Troubleshooting

### "BLOCKED: Cannot edit files in main directory"

You're trying to edit without a worktree:
```bash
make worktree    # Create workspace first
```

### "BLOCKED: Direct 'git worktree add' is not allowed"

Use the proper command:
```bash
make worktree    # Instead of git worktree add
```

### "Commit message must start with [Plan #N] or [Trivial]"

Fix your commit message:
```bash
git commit -m "[Plan #1] Your description"
# or
git commit -m "[Trivial] Fix typo"
```

### Hooks not running at all

Check git config:
```bash
git config core.hooksPath
# Should output: hooks
```

If empty or wrong:
```bash
git config core.hooksPath hooks
```

### Hook blocks legitimate operation

For emergencies, bypass with:
```bash
# Git hooks
git commit --no-verify -m "..."

# Claude Code hooks - edit meta-process.yaml to disable
```

---

## Planning Pattern Hooks

These hooks validate planning patterns in plan files. See [Question-Driven Planning](../patterns/28_question-driven-planning.md) and [Uncertainty Tracking](../patterns/29_uncertainty-tracking.md).

### check-planning-patterns.sh

**Purpose:** Validate planning patterns when editing plan files.

**Checks:**
- Open Questions section exists
- No unverified claims ("I believe", "might be", etc.)
- No prohibited terms from conceptual model

**Configuration (meta-process.yaml):**
```yaml
planning:
  question_driven_planning: advisory  # disabled | advisory | required
  uncertainty_tracking: advisory
  warn_on_unverified_claims: true
  warn_on_prohibited_terms: true
```

**Behavior by level:**
- `disabled` - No checks
- `advisory` - Warnings only (default)
- `required` - Errors block operation

### pre-commit-planning-patterns.sh

**Purpose:** Validate planning patterns in plan files before commit.

**Usage:** Add to your pre-commit hook chain:
```bash
# In hooks/pre-commit
source meta-process/hooks/pre-commit-planning-patterns.sh
```

### Validation Script

For standalone validation:
```bash
# Check single plan
python scripts/check_planning_patterns.py --plan 229

# Check all plans
python scripts/check_planning_patterns.py --all

# Strict mode (advisory becomes required)
python scripts/check_planning_patterns.py --plan 229 --strict
```

### CI Integration

Copy `meta-process/ci/planning-patterns.yml` to `.github/workflows/` to enable CI validation.

The CI workflow:
- Runs on PRs that modify plan files
- Uses `advisory` mode by default
- Uses `required` mode when `weight: heavy`

## See Also

- [Git Hooks Pattern](../patterns/06_git-hooks.md)
- [Worktree Enforcement Pattern](../patterns/19_worktree-enforcement.md)
- [Claim System Pattern](../patterns/18_claim-system.md)
- [Question-Driven Planning](../patterns/28_question-driven-planning.md)
- [Uncertainty Tracking](../patterns/29_uncertainty-tracking.md)
- [Conceptual Modeling](../patterns/27_conceptual-modeling.md)
