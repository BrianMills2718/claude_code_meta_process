# Getting Started with Meta-Process

A step-by-step guide to adopting the meta-process framework for AI-assisted development.

## What is Meta-Process?

Meta-process is a collection of patterns for coordinating AI coding assistants (Claude Code, Cursor, etc.) on shared codebases. It solves problems like:

- **Parallel work conflicts** - Multiple instances editing the same files
- **Context loss** - AI forgetting project conventions mid-session
- **Documentation drift** - Docs diverging from code over time
- **Unverified completions** - "Done" work that doesn't actually work
- **AI drift** - AI guessing instead of investigating, making wrong assumptions

---

## Choose Your Weight Level

Before starting, decide how much process overhead you want:

| Weight | Best For | Planning Patterns | Enforcement |
|--------|----------|-------------------|-------------|
| **minimal** | Quick experiments, spikes | None | Almost nothing |
| **light** | Prototypes, solo work | Advisory (warnings) | Warnings only |
| **medium** | Most projects (default) | Advisory + templates | Balanced |
| **heavy** | Critical/regulated projects | Required + validation | Full enforcement |

### Planning Patterns (New in v2)

These patterns improve planning quality and reduce AI drift:

| Pattern | What It Does | When to Use |
|---------|--------------|-------------|
| [Question-Driven Planning](patterns/28_question-driven-planning.md) | Surface questions BEFORE solutions | Always (low overhead) |
| [Uncertainty Tracking](patterns/29_uncertainty-tracking.md) | Track unknowns across sessions | Medium+ projects |
| [Conceptual Modeling](patterns/27_conceptual-modeling.md) | Define "what things ARE" | Complex architectures |

**The core principle:** Don't guess, verify. Every "I believe" should become "I verified by reading X".

### Configure in meta-process.yaml

```yaml
# Choose your weight
weight: medium  # minimal | light | medium | heavy

# Fine-tune planning patterns
planning:
  question_driven_planning: advisory  # disabled | advisory | required
  uncertainty_tracking: advisory
  conceptual_modeling: disabled       # Enable for complex projects
  warn_on_unverified_claims: true     # Warn on "I believe", "might be"
```

### Project Type Guidance

| If your project is... | Start with... |
|-----------------------|---------------|
| **New + Simple** | `weight: light`, planning: advisory |
| **New + Complex** | `weight: medium`, enable conceptual_modeling |
| **Existing + Adding meta-process** | `weight: light` first, increase over time |
| **Regulated/Critical** | `weight: heavy`, all patterns required |

---

## Quick Start (30 minutes)

### Step 1: Install

```bash
# From your project root
./meta-process/install.sh . --minimal
```

This creates:
- `meta-process.yaml` - Configuration
- `docs/plans/` - Work tracking
- `hooks/` - Git hooks
- `.claude/hooks/` - Claude Code hooks
- `scripts/meta/` - Utility scripts

### Step 2: Configure

Edit `meta-process.yaml`:

```yaml
# Start with these enabled
enabled:
  plans: true           # Track work in plan files
  claims: true          # Prevent parallel conflicts
  worktrees: true       # File isolation
  git_hooks: true       # Pre-commit checks

# Disable until ready
disabled:
  doc_coupling: true    # Add later
  acceptance_gates: true
```

### Step 3: Verify

```bash
make status              # Should show clean state
python scripts/meta/check_claims.py --list   # Should show no claims
```

### Step 4: Test the Workflow

```bash
# 1. Create a workspace
make worktree
# Enter: "Test meta-process setup"
# Enter: (blank for no plan)
# Enter: "test-setup"

# 2. Make a trivial change
echo "# Test" >> worktrees/test-setup/README.md

# 3. Commit
git -C worktrees/test-setup add -A
git -C worktrees/test-setup commit -m "[Trivial] Test setup"

# 4. Clean up
make worktree-remove BRANCH=test-setup
```

If that worked, you're ready!

---

## First Week Adoption Path

### Day 1-2: Core Workflow

**Goal:** Get comfortable with worktrees and claims.

1. **Read patterns:**
   - [CLAUDE.md Authoring](patterns/02_claude-md-authoring.md) - Project context
   - [Worktree Enforcement](patterns/19_worktree-enforcement.md) - File isolation
   - [Claim System](patterns/18_claim-system.md) - Coordination

2. **Set up your CLAUDE.md:**
   ```markdown
   # Project Name

   ## Quick Reference
   - `make test` - Run tests
   - `make worktree` - Create workspace

   ## Design Principles
   1. Fail loud - No silent errors
   2. Test first - Write tests before code

   ## Key Rules
   - Always use worktrees for implementation
   - Commit messages: `[Plan #N]` or `[Trivial]`
   ```

3. **Practice the workflow:**
   ```bash
   make worktree      # Start work
   # ... edit files ...
   git -C worktrees/X commit -m "[Trivial] ..."
   git -C worktrees/X push -u origin X
   gh pr create --head X
   make finish BRANCH=X PR=N
   ```

### Day 3-4: Plans

**Goal:** Track work in plan files.

1. **Read patterns:**
   - [Plan Workflow](patterns/15_plan-workflow.md)
   - [Plan Status Validation](patterns/23_plan-status-validation.md)

2. **Create your first plan:**
   ```bash
   # Copy template
   cp docs/plans/TEMPLATE.md docs/plans/001_my_first_plan.md

   # Edit to describe your task
   ```

3. **Use plans in workflow:**
   ```bash
   make worktree
   # Enter plan number: 1
   # Creates: worktrees/plan-1-my_first_plan/
   ```

### Day 5-7: Git Hooks

**Goal:** Catch issues before CI.

1. **Read patterns:**
   - [Git Hooks](patterns/06_git-hooks.md)

2. **Install hooks:**
   ```bash
   git config core.hooksPath hooks
   ```

3. **Test hooks:**
   ```bash
   # Try a bad commit message
   git commit --allow-empty -m "bad message"
   # Should fail with: "Commit message must start with [Plan #N] or [Trivial]"
   ```

---

## Second Week: Enhanced Quality

### Enable Doc-Code Coupling

1. **Read:** [Doc-Code Coupling](patterns/10_doc-code-coupling.md)

2. **Configure mappings:**
   ```yaml
   # scripts/doc_coupling.yaml
   couplings:
     - sources: ["src/api/*.py"]
       docs: ["docs/api.md"]
       description: "API documentation"
   ```

3. **Enable in meta-process.yaml:**
   ```yaml
   enabled:
     doc_coupling: true
   ```

### Add Mock Enforcement

1. **Read:** [Mock Enforcement](patterns/05_mock-enforcement.md)

2. **Run check:**
   ```bash
   python scripts/meta/check_mock_usage.py
   ```

---

## Key Concepts

### Always Run From Main

Your working directory should always be the main repo:

```bash
# CORRECT - Use worktree as a path
cd /repo                           # Stay in main
vim worktrees/plan-1/src/file.py   # Edit via path
git -C worktrees/plan-1 commit     # Commit via -C flag

# WRONG - Don't cd into worktree
cd /repo/worktrees/plan-1          # If worktree deleted, shell breaks
vim src/file.py
git commit
```

**Why?** If you're inside a worktree and it gets deleted (after merge), your shell's working directory becomes invalid.

> For detailed explanation with examples, see [Understanding CWD and Paths](UNDERSTANDING_CWD.md).

### Claims Prevent Conflicts

Before starting work, you claim it:

```bash
make worktree     # Automatically creates claim
```

Other instances see your claim:

```bash
python scripts/meta/check_claims.py --list
# Active claims:
#   plan-1-feature  ->  Plan #1: Add feature X
```

They know not to work on the same thing.

### Commit Message Convention

```bash
[Plan #N] Description    # Links to plan file
[Trivial] Fix typo       # For tiny changes (<20 lines, no src/)
```

The git hook enforces this.

---

## Troubleshooting

### "BLOCKED: Cannot edit files in main directory"

You tried to edit without a worktree:

```bash
# Fix: Create a worktree first
make worktree
# Then edit files in worktrees/your-branch/
```

### "Conflict detected. Another instance is working on this plan"

Someone else claimed this work:

```bash
# Check who
python scripts/meta/check_claims.py --list

# Either:
# 1. Work on something else
# 2. Wait for them to finish
# 3. Coordinate directly
```

### "Commit message must start with [Plan #N] or [Trivial]"

Your commit message doesn't follow the convention:

```bash
# Fix: Use proper prefix
git commit -m "[Trivial] Fix typo in README"
# or
git commit -m "[Plan #1] Add user authentication"
```

### Hooks not running

```bash
# Check hook path
git config core.hooksPath
# Should be: hooks

# Fix if wrong
git config core.hooksPath hooks
```

> For complete hook documentation, see [Hooks Overview](hooks/README.md).

---

## Next Steps

After completing the basics:

1. **Adopt planning patterns** - Improve AI planning quality
   - Start with: [Question-Driven Planning](patterns/28_question-driven-planning.md) (low overhead)
   - Add: [Uncertainty Tracking](patterns/29_uncertainty-tracking.md) when context loss is painful
   - Consider: [Conceptual Modeling](patterns/27_conceptual-modeling.md) for complex architectures

2. **Add acceptance gates** - Verify work actually works before marking complete
   - See: [Acceptance-Gate-Driven Development](patterns/13_acceptance-gate-driven-development.md)

3. **Add ADRs** - Preserve architectural decisions
   - See: [ADR](patterns/07_adr.md), [ADR Governance](patterns/08_adr-governance.md)

4. **Add inter-CC messaging** - Coordinate between Claude Code instances
   - See: `scripts/send_message.py`, `scripts/check_messages.py`

---

## Quick Reference

| Task | Command |
|------|---------|
| Check status | `make status` |
| Create workspace | `make worktree` |
| List workspaces | `make worktree-list` |
| See claims | `python scripts/meta/check_claims.py --list` |
| Run tests | `make test` |
| Run checks | `make check` |
| Prepare PR | `make pr-ready` |
| Create PR | `make pr` |
| Finish work | `make finish BRANCH=X PR=N` |

---

## Patterns by Adoption Stage

| Stage | Patterns | Effort |
|-------|----------|--------|
| **Week 1** | CLAUDE.md, Worktrees, Claims, Plans | Low |
| **Week 1** | Question-Driven Planning (use plan template) | Low |
| **Week 2** | Git Hooks, Doc-Code Coupling | Low |
| **Week 2** | Uncertainty Tracking (in plans) | Low |
| **Month 1** | Mock Enforcement, Plan Verification | Medium |
| **When needed** | Conceptual Modeling (complex architectures) | Medium |
| **Later** | ADRs, Acceptance Gates, Full Graph | High |

Start small. Add patterns when you feel the pain they solve.

### Planning Pattern Adoption

The new planning patterns have minimal overhead:

1. **Question-Driven Planning** - Just use the updated plan template. Fill in "Open Questions" before "Plan".

2. **Uncertainty Tracking** - Track uncertainties in the plan's table. Update status as you resolve them.

3. **Conceptual Modeling** - Only add when AI instances repeatedly misunderstand your architecture. Create `docs/CONCEPTUAL_MODEL.yaml` with your core concepts.
