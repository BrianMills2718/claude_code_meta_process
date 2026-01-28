# Claude Code Meta-Process Template v0.1

**Purpose**: Reusable coordination patterns for AI-assisted development with Claude Code.

**Scope**: Single or multi-instance, greenfield or existing codebases.

---

## Configuration Schema

```yaml
# .claude/template-config.yaml

# === PROJECT CONTEXT ===
project:
  state: existing | greenfield          # Existing codebase vs new project
  cc_instances: single | multi          # One Claude Code or parallel instances

# === ENFORCEMENT LEVELS ===
# Gradations: hook (hard block) > ci (blocks merge) > warning > honor
enforcement:
  preset: strict | balanced | lenient   # Quick selection

  # Granular overrides (optional)
  overrides:
    plan_required: ci              # Require plan for non-trivial work
    test_before_merge: ci          # Tests must pass
    doc_coupling: warning          # Docs should match code
    claim_required: hook           # Multi-CC: must claim work
    worktree_required: hook        # Multi-CC: no edits in main

# === PRESETS (what each level sets) ===
# strict:   All at 'ci' or 'hook' level, plus pre-commit hooks
# balanced: plan_required=ci, test=ci, doc_coupling=warning, claims=hook
# lenient:  plan_required=warning, test=ci, doc_coupling=honor, claims=warning

# === WORK ORGANIZATION ===
work:
  primary: plans                   # Plans are the work unit (not features)
  trivial_exemption: true          # Allow [Trivial] for small changes
  trivial_max_lines: 20            # Max lines for trivial
  trivial_excludes:                # Trivial can't touch these
    - "src/"
    - "config/"

# === DOCUMENTATION ===
documentation:
  coupling:
    enabled: true
    strictness: warning            # ci | warning | honor
    mappings_file: scripts/doc_coupling.yaml

  glossary:
    location: docs/GLOSSARY.md     # Single source of truth
    enforce_terms: true            # Warn on term violations

  architecture:
    current_dir: docs/architecture/current/   # What IS implemented
    plans_dir: docs/plans/                    # Work items
    # NOTE: No target/ directory. PRD + ADRs capture architectural intent.
    # ADRs = specific decisions, PRD = overall requirements

# === MULTI-CC COORDINATION (only if cc_instances: multi) ===
coordination:
  claims_file: .claude/active-work.yaml
  worktrees_dir: worktrees/
  hooks:
    - check_claims.py              # Verify work is claimed
    - check_worktree.py            # Block edits in main directory
```

---

## Directory Structure

### Minimal Core (All Projects)

```
project/
├── CLAUDE.md                      # Root: universal rules, philosophy
├── .claude/
│   ├── template-config.yaml       # Template configuration
│   └── settings.json              # Claude Code settings
├── docs/
│   ├── CLAUDE.md                  # Contextual: doc-specific rules
│   ├── GLOSSARY.md                # Single terminology source
│   └── plans/
│       ├── CLAUDE.md              # Plan template and workflow
│       └── NN_plan_name.md        # Individual plans
└── src/
    └── CLAUDE.md                  # Contextual: code conventions
```

### Extended (Mature Projects)

```
project/
├── ...core structure above...
├── docs/
│   ├── architecture/
│   │   └── current/              # What IS implemented
│   │   # NOTE: No target/. Use PRD for requirements, ADRs for decisions.
│   ├── adr/                      # Architecture Decision Records
│   ├── acceptance_gates/                 # E2E acceptance definitions
│   │   └── NN_feature_name.md    # Feature with acceptance criteria
│   └── meta/                     # Reusable process patterns
├── scripts/
│   ├── doc_coupling.yaml         # Doc-to-code mappings
│   ├── check_doc_coupling.py     # Coupling enforcement
│   └── governance.yaml           # ADR-to-file mappings
└── .github/
    └── workflows/
        └── ci.yml                # CI with enforcement checks
```

### Multi-CC Extended

```
project/
├── ...extended structure above...
├── .claude/
│   ├── active-work.yaml          # Current claims
│   └── hooks/
│       ├── pre-commit-check-claim.sh
│       └── pre-commit-check-worktree.sh
└── worktrees/                    # Isolated per-instance directories
    ├── plan-01-feature/
    └── plan-02-bugfix/
```

---

## Core Modules

### 1. CLAUDE.md Hierarchy (Required)

**Principle**: Contextual, compendious (minimize tokens while maximizing relevance)

| File | Contains | Loaded When |
|------|----------|-------------|
| `/CLAUDE.md` | Philosophy, universal rules, **Code Map**, quick reference | Always |
| `/docs/CLAUDE.md` | Doc conventions, update protocols | In docs/ |
| `/src/CLAUDE.md` | Code style, testing rules, typing, **detailed code map for src/** | In src/ |
| `/docs/plans/CLAUDE.md` | Plan template, workflow | Working on plans |

**Rules**:
- Root CLAUDE.md: Max 500 lines, links to details elsewhere
- Subdirectory CLAUDE.md: Max 200 lines, specific to that context
- Never duplicate content between hierarchy levels

**Code Map Requirement** (enforced):

Root CLAUDE.md MUST include a basic Code Map:
```markdown
## Code Map
| Domain | Location | Purpose |
|--------|----------|---------|
| Core simulation | src/simulation/ | SimulationRunner, tick loop |
| World state | src/world/ | Ledger, artifacts, executor |
| Agents | src/agents/ | Agent loading, LLM interaction |
| Config | config/ | Runtime configuration |
```

Subdirectory CLAUDE.md files supplement with detail:
```markdown
# src/CLAUDE.md
## Code Map (src/)
| File | Key Elements | Purpose |
|------|--------------|---------|
| world/ledger.py | Ledger class, transfer() | Balance management |
| world/executor.py | Executor class, run_action() | Action execution |
| agents/agent.py | Agent class, decide() | Agent decision loop |
```

**Enforcement**:
- CI validates Code Map references actual files (no stale entries)
- Doc-coupling: src changes trigger CLAUDE.md update check
- Hook can warn if editing file not in Code Map

### 2. Plans Workflow (Required)

**Plans are work coordination units** - they track what needs doing and coordinate multi-CC work.

```yaml
# docs/plans/NN_plan_name.md structure
---
status: "🚧 In Progress"  # or ✅ Complete, 📋 Planned
---

## Problem Statement
What problem does this solve?

## References Reviewed
# REQUIRED: Cite specific code/docs reviewed before planning
# Forces CC to explore before coding - prevents guessing
- src/world/executor.py:45-89 - existing action handling
- src/world/ledger.py:120-150 - balance update logic
- docs/architecture/current/actions.md - action design
- CLAUDE.md - project conventions

## Files Affected
# REQUIRED: Declare upfront what files will be touched
- src/world/executor.py (modify)
- src/world/rate_limiter.py (create)
- tests/test_rate_limiter.py (create)
- config/schema.yaml (modify)

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Plan
Step-by-step implementation route.

## Required Tests
- test_function_name: What it validates

## Verification Evidence
<!-- Filled by completion script -->
```

**Files Affected Enforcement**:
- Plans MUST declare files upfront
- Claiming a plan locks those files from other plans
- Hook blocks edits to undeclared files: "File not in plan scope. Update plan first."
- Creates automatic dependency graph (plans sharing files = dependency)
- Traceability: every file change traces to a plan

**Lifecycle**:
1. Create plan with files affected + acceptance criteria
2. Claim work (multi-CC) - locks declared files
3. Implement with TDD (hook enforces file scope)
4. If touching new file: update plan's Files Affected first
5. Complete via script (validates tests, updates status atomically)

### 3. Trivial Exemption (Required)

**Purpose**: Reduce friction for small changes without abandoning traceability.

```bash
# Valid trivial commit
git commit -m "[Trivial] Fix typo in README"

# Criteria (ALL must be true):
# - Less than N lines changed (configurable, default 20)
# - No changes to excluded paths (src/, config/)
# - No new files created
# - No test logic changes (typo fixes ok)
```

CI validates trivial commits don't exceed configured limits.

### 4. Features as E2E Acceptance Gates (Recommended)

**Features are testable capabilities** - coherent units that can be verified end-to-end.

**The problem Features solve:**
```
CC workflow without features:
1. Write code for 3 days
2. Write mocked unit tests (pass!)
3. Say "done"
4. User runs → everything broken
5. Codebase is unsalvageable
```

**Feature definition:**
```markdown
# docs/acceptance_gates/NN_feature_name.md

## Feature: Agent Resource Trading

### Scope
Agents can exchange resources using the ledger and escrow systems.

### Acceptance Criteria (LLM-Verifiable)
1. Agents can transfer scrip to each other
2. Ledger balances update correctly
3. Agents make economically rational trades (LLM-verified)
4. No agent goes negative without debt contract

### E2E Test
- Run: `python run.py --ticks 10 --agents 3`
- Programmatic checks: criteria 1-2
- LLM review: criteria 3-4 (review logs against criteria)

### Status
- [ ] E2E test passes
- [ ] LLM review approved
```

**Key distinctions:**
| Concept | Purpose | Granularity |
|---------|---------|-------------|
| Plan | Work coordination, file locking | Task-level |
| Feature | E2E acceptance verification | Capability-level |

- A plan might partially implement a feature
- A feature might require multiple plans
- Plans coordinate CC instances (who works on what)
- Features define "actually done" for users (does it work?)

**Verification:**
- Features require REAL execution (no mocks)
- Programmatic checks for objective criteria
- LLM review for semantic criteria ("behavior is sensible")
- Example: simulation runs but agents act randomly = feature FAILS

### 5. Doc Coupling (Required, Configurable Strictness)

**Purpose**: Ensure documentation matches code.

```yaml
# scripts/doc_coupling.yaml
mappings:
  - source: src/world/ledger.py
    docs:
      - docs/architecture/current/resources.md
    type: strict     # CI fails if source changes without doc update

  - source: src/config_schema.py
    docs:
      - docs/architecture/current/configuration.md
    type: soft       # Warning only
```

**Future expansion**: Code graph coupling (function-level, not just file-level)

---

## Optional Modules

### 5. Multi-CC Coordination (If cc_instances: multi)

**Claims System**:
```yaml
# .claude/active-work.yaml
claims:
  - cc_id: plan-48-ci-optimization
    plan: 48
    task: "Optimize CI workflow"
    claimed_at: 2026-01-16T14:21:00
```

**Worktree Enforcement**:
```bash
# Pre-commit hook blocks edits in main directory
if [ "$PWD" = "$(git rev-parse --show-toplevel)" ]; then
  echo "ERROR: Cannot edit files in main. Use make worktree BRANCH=..."
  exit 1
fi
```

**Why This Matters**: Investigation found 20 dangling commits - duplicate work from multi-CC conflicts. Worktree enforcement prevents this.

### 6. ADR Governance (Mature Projects)

**Purpose**: Link architecture decisions to code that implements them.

```yaml
# scripts/governance.yaml
adr-0001-everything-artifact:
  files:
    - src/world/genesis.py
    - src/world/ledger.py
```

Files get headers showing which ADRs govern them. CI ensures sync.

### 7. ~~Target Architecture~~ (REMOVED)

**Decision:** Kill `target/` directory. PRD + ADRs are sufficient.

- **PRD**: Overall requirements ("I want escrow functionality")
- **ADRs**: Specific technical decisions ("Use optimistic locking for escrow")
- **Plans**: Work items to implement ("Implement escrow phase 1")

If someone wants a synthesized architecture diagram, treat it as a point-in-time artifact, not a maintained document.

---

## Enforcement Presets

### Strict
```yaml
enforcement:
  preset: strict
  # Equivalent to:
  overrides:
    plan_required: hook      # Can't commit without plan reference
    test_before_merge: hook  # Pre-commit runs tests
    doc_coupling: ci         # Fails CI if docs outdated
    claim_required: hook     # Multi-CC: must claim first
    worktree_required: hook  # Multi-CC: no main edits
```

### Balanced (Recommended)
```yaml
enforcement:
  preset: balanced
  # Equivalent to:
  overrides:
    plan_required: ci        # CI checks plan reference
    test_before_merge: ci    # CI runs tests
    doc_coupling: warning    # Warns but doesn't block
    claim_required: hook     # Multi-CC: must claim first
    worktree_required: hook  # Multi-CC: no main edits
```

### Lenient
```yaml
enforcement:
  preset: lenient
  # Equivalent to:
  overrides:
    plan_required: warning   # Warns about missing plan
    test_before_merge: ci    # Still require tests
    doc_coupling: honor      # Trust developers
    claim_required: warning  # Multi-CC: warn if unclaimed
    worktree_required: honor # Multi-CC: trust developers
```

---

## Migration Guide

### From Nothing (Greenfield)
1. Create `CLAUDE.md` with philosophy and rules
2. Create `docs/plans/` with first plan
3. Add `.claude/template-config.yaml` with `lenient` preset
4. Increase enforcement as team grows

### From Existing Process
1. Audit current patterns (what's actually used vs aspirational)
2. Map existing docs to new structure
3. Start with `balanced` preset
4. Kill unused patterns (e.g., features.yaml if claims are plan-based)
5. Consolidate redundant docs (e.g., multiple glossaries)

### Adding Multi-CC
1. Add `coordination` section to config
2. Create `.claude/active-work.yaml`
3. Add pre-commit hooks for claims and worktrees
4. Document worktree workflow in CLAUDE.md

---

## Anti-Patterns (From Investigation)

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| File-scope ownership (features.yaml) | Tedious to maintain, redundant with plans | Plans declare files upfront, hook enforces |
| Target architecture docs | Drifts from ADRs, maintenance burden | Kill target/, use PRD + ADRs |
| Multiple glossaries | Inconsistency | Single GLOSSARY.md |
| Honor-system claims | Work overwrites | Hook-based enforcement |
| Editing in main directory | Conflicts, lost work | Mandatory worktrees for multi-CC |
| Big-bang development | Mocked tests pass, real system broken | Features as E2E acceptance gates |
| Plans without file declarations | Undiscovered conflicts, no traceability | Require Files Affected section |
| Coding without exploration | CC guesses, breaks things | Require References Reviewed section |
| Stale CLAUDE.md | CC can't find relevant code | Code Map + validation enforcement |

---

## CC-Specific Considerations

This template is optimized for **Claude Code instances as developers**. Key differences from human teams:

### CC Strengths to Leverage
- Parallel execution (multiple worktrees)
- Consistent rule-following (if enforced by hooks)
- No ego about code ownership
- Can process large codebases quickly

### CC Weaknesses to Mitigate

| Weakness | Human Impact | CC Impact | Mitigation |
|----------|--------------|-----------|------------|
| Over-engineering | Medium | **HIGH** | Strict acceptance criteria, "minimal solution" emphasis |
| Mock abuse | Low | **HIGH** | Hook blocks mocks without `# mock-ok:` justification |
| Scope creep | Medium | **HIGH** | File declarations enforced by hook |
| Skipping exploration | Low | **HIGH** | References Reviewed required, Code Map in CLAUDE.md |
| Ignoring existing code | Low | **HIGH** | Must cite existing code in References Reviewed |
| Breaking changes | Medium | **HIGH** | E2E tests mandatory, not just unit tests |
| Guessing file locations | Low | **HIGH** | Code Map provides discoverable index |

### Enforcement Philosophy

**Prefer hooks over social pressure.** CC doesn't respond to "you should" - it responds to "you cannot."

| Enforcement Type | For Humans | For CC |
|------------------|------------|--------|
| Guidelines in docs | Works well | Often ignored |
| Code review | Catches issues | Too late - CC already built wrong thing |
| CI failures | Good | Good but slow feedback loop |
| **Pre-edit hooks** | Annoying | **Ideal - immediate feedback** |

CC works best with immediate, automated feedback at the moment of action, not delayed review.

---

## Checklist for New Projects

- [ ] Create root `CLAUDE.md` with philosophy
- [ ] Create `docs/plans/CLAUDE.md` with plan template (include Files Affected section)
- [ ] Create `.claude/template-config.yaml`
- [ ] Set enforcement preset based on team/risk
- [ ] If multi-CC: Add claims and worktree hooks
- [ ] Add hook to enforce plan file scope (block undeclared file edits)
- [ ] Create first plan before first code change
- [ ] Add doc coupling for critical files
- [ ] Define first feature with E2E acceptance criteria

---

## Reference Implementation (agent_ecology)

### Hooks That Exist

| Hook | Trigger | Purpose | Status |
|------|---------|---------|--------|
| `protect-main.sh` | Edit/Write | Blocks file edits in main directory | ✅ Working |
| `block-worktree-remove.sh` | Bash | Blocks `git worktree remove` commands | ✅ Working |
| `protect-uncommitted.sh` | Bash | Warns about uncommitted work in commands | ✅ Working |

### Hooks To Build (Committed)

These hooks will be implemented as part of this template:

| Hook | Trigger | Purpose | Priority |
|------|---------|---------|----------|
| `verify-claim.sh` | Edit/Write | Verify work is claimed before edits | HIGH |
| `check-file-scope.sh` | Edit/Write | Block edits to files not in plan's Files Affected | HIGH |
| `check-references-reviewed.sh` | Edit/Write | Warn if plan lacks References Reviewed section | HIGH |
| `validate-code-map.sh` | CI | Verify CLAUDE.md Code Map references existing files | HIGH |
| `check-plan-prefix.sh` | Bash (git commit) | Verify `[Plan #N]` or `[Trivial]` prefix | MEDIUM |
| `verify-feature-e2e.sh` | PR merge | Run feature E2E tests before merge | MEDIUM |

**Hook Logic Details:**

`check-file-scope.sh`:
```bash
# 1. Get current plan from worktree name or active claim
# 2. Parse plan's "## Files Affected" section
# 3. Check if $EDIT_FILE is in the list
# 4. If not: block with "File not in plan scope. Update plan first."
```

`check-references-reviewed.sh`:
```bash
# 1. Get current plan file
# 2. Check for "## References Reviewed" section
# 3. Verify it has at least 2 entries with line numbers
# 4. If empty/missing: warn "Plan lacks References Reviewed. Explore first."
```

`validate-code-map.sh`:
```bash
# 1. Parse CLAUDE.md Code Map table
# 2. For each file/directory listed, verify it exists
# 3. Report stale entries (listed but doesn't exist)
# 4. Optionally: report undocumented src files
```

### Settings.json Configuration

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {"type": "command", "command": "bash .claude/hooks/protect-main.sh"}
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {"type": "command", "command": "bash .claude/hooks/block-worktree-remove.sh"},
          {"type": "command", "command": "bash .claude/hooks/protect-uncommitted.sh"}
        ]
      }
    ]
  }
}
```

---

## CLAUDE.md Hierarchy Best Practices

### Recommended Structure

| Level | File | Max Lines | Contains |
|-------|------|-----------|----------|
| Root | `/CLAUDE.md` | 500 | Philosophy, universal rules, quick reference |
| Docs | `/docs/CLAUDE.md` | 200 | Doc conventions, update protocols |
| Source | `/src/CLAUDE.md` | 200 | Code style, testing, typing rules |
| Plans | `/docs/plans/CLAUDE.md` | 200 | Plan template, workflow |

### What Goes Where

**Root CLAUDE.md:**
- Project philosophy and goals
- Critical warnings (worktree enforcement, claim requirements)
- Quick command reference
- Links to detailed docs

**Subdirectory CLAUDE.md:**
- Context-specific rules only
- Never duplicate root content
- Link back to root for universal rules

### Anti-Pattern: Bloated Root

❌ **Bad**: Root CLAUDE.md with 2000+ lines covering everything
- Wastes tokens on every load
- Hard to maintain
- CC may ignore due to length

✅ **Good**: Root ~300-500 lines with links to subdirectory CLAUDE.md
- Contextual loading (only loads what's needed)
- Easier to maintain
- Clear separation of concerns

---

## Decisions Log

Decisions made during template development, with rationale:

### Adopted

| Decision | Rationale | Enforcement |
|----------|-----------|-------------|
| Kill features.yaml | Never used in practice, redundant with plans | N/A (removed) |
| Single GLOSSARY.md | Multiple glossaries caused inconsistency | Doc coupling |
| Hooks > CI | CC needs immediate feedback, not delayed | PreToolUse hooks |
| Worktree mandatory | Multi-CC in same dir = corrupted work | Hook blocks main edits |
| Kill target/ architecture | Drifts from ADRs, PRD + ADRs sufficient | N/A (removed) |
| Plans declare files upfront | Forces planning, creates traceability, prevents guessing | Hook blocks undeclared |
| Features = E2E gates | Prevents big-bang development with mocked tests | E2E required for completion |
| References Reviewed required | Forces CC to explore before coding | Hook warns if missing |
| Code Map in CLAUDE.md | CC needs discoverable index to find code | CI validates accuracy |
| Shared references symlink | Reference docs shared across worktrees without git | create_worktree.sh |

### Deferred

| Decision | Reason Deferred |
|----------|-----------------|
| Function/class level scoping | Marginal value vs complexity; file-level is 90% of benefit |
| Automatic dependency graph | Value unclear; file overlap ≠ true dependency |
| Naming conventions for greppability | Marginal; Code Map solves discoverability better |

### Rejected

| Decision | Reason Rejected |
|----------|-----------------|
| Review step for plan approval | Prefer stricter enforcement over social process |
| Sparse checkout for worktrees | Too restrictive; CC needs to read files it won't edit |

---

## Version History

- **v0.1.2** (2026-01-17): Exploration and Code Map requirements
  - Added "References Reviewed" required section in plans (forces exploration)
  - Added Code Map requirement in CLAUDE.md hierarchy
  - Added CLAUDE.md enforcement (CI validates Code Map, doc-coupling)
  - Documented hooks to build: check-file-scope, check-references-reviewed, validate-code-map
  - Added CC-specific considerations section (strengths/weaknesses/enforcement philosophy)
  - Emphasis: hooks over guidelines, immediate feedback over review

- **v0.1.1** (2026-01-17): Major refinements from template discussion
  - Removed `target/` architecture - PRD + ADRs sufficient
  - Added plan-declared file scopes with hook enforcement
  - Added Features as E2E acceptance gates (real runs, LLM verification)
  - Clarified Plans (work coordination) vs Features (acceptance verification)
  - Added anti-patterns: big-bang development, plans without file declarations

- **v0.1** (2026-01-17): Initial spec based on agent_ecology investigation
  - 23 patterns audited, 14 active, 5 partial, 3 aspirational
  - 20 dangling commits analyzed (duplicate work, not lost)
  - Simplified from features+plans to plans-only
  - Added enforcement presets
