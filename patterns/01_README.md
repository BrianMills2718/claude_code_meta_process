# Meta Patterns

Reusable development process patterns. Each pattern solves a specific coordination or quality problem when working with AI coding assistants (Claude Code, etc.).

> **New to meta-process?** Start with the [Getting Started Guide](../GETTING_STARTED.md) for a step-by-step onboarding path.

## Pattern Index

| Pattern | Problem Solved | Complexity |
|---------|----------------|------------|
| [CLAUDE.md Authoring](02_claude-md-authoring.md) | AI assistants lack project context | Low |
| [Testing Strategy](03_testing-strategy.md) | Inconsistent test approaches | Low |
| [Mocking Policy](04_mocking-policy.md) | When to mock, when not to | Low |
| [Mock Enforcement](05_mock-enforcement.md) | Green CI, broken production | Low |
| [Git Hooks](06_git-hooks.md) | CI failures caught late | Low |
| [ADR](07_adr.md) | Architectural decisions get lost | Medium |
| [ADR Governance](08_adr-governance.md) | ADRs not linked to code | Medium |
| [Documentation Graph](09_documentation-graph.md) | Can't trace decisions → code | Medium |
| [Doc-Code Coupling](10_doc-code-coupling.md) | Docs drift from code | Medium |
| [Terminology](11_terminology.md) | Inconsistent terms | Low |
| [Structured Logging](12_structured-logging.md) | Unreadable logs | Low |
| [Acceptance-Gate-Driven Development](13_acceptance-gate-driven-development.md) | AI drift, cheating, big bang integration | High |
| [Acceptance Gate Linkage](14_acceptance-gate-linkage.md) | Sparse file-to-constraint mappings | Medium |
| [Plan Workflow](15_plan-workflow.md) | Untracked work, scope creep | Medium |
| [Plan Blocker Enforcement](16_plan-blocker-enforcement.md) | Blocked plans started anyway | Medium |
| [Verification Enforcement](17_verification-enforcement.md) | Untested "complete" work | Medium |
| [Claim System](18_claim-system.md) | Parallel work conflicts | Medium |
| [Worktree Enforcement](19_worktree-enforcement.md) | Main directory corruption from parallel edits | Low |
| [Rebase Workflow](20_rebase-workflow.md) | Stale worktrees causing "reverted" changes | Low |
| [PR Coordination](21_pr-coordination.md) | Lost review requests | Low |
| [Human Review Pattern](22_human-review-pattern.md) | Risky changes merged without review | Medium |
| [Plan Status Validation](23_plan-status-validation.md) | Status/content mismatch in plans | Low |
| [Phased ADR Pattern](24_phased-adr-pattern.md) | Complex features need phased rollout | Medium |
| [PR Review Process](25_pr-review-process.md) | Inconsistent review quality | Low |
| [Ownership Respect](26_ownership-respect.md) | CC instances interfering with each other's work | Low |
| [Conceptual Modeling](27_conceptual-modeling.md) | AI accumulates misconceptions about architecture | Medium |
| [Question-Driven Planning](28_question-driven-planning.md) | AI guesses instead of investigating | Low |
| [Uncertainty Tracking](29_uncertainty-tracking.md) | Uncertainties forgotten across sessions | Low |

## When to Use

**Start with these (low overhead):**
- CLAUDE.md Authoring - any project using AI coding assistants
- Mock Enforcement - if using pytest with mocks
- Git Hooks - any project with CI
- PR Coordination - if multiple people/instances work in parallel
- Worktree Enforcement - if multiple Claude Code instances share a repo
- Rebase Workflow - when using worktrees for parallel work (prevents "reverted" changes)
- PR Review Process - standardized review checklists
- Ownership Respect - prevent CC instances from fixing each other's work
- Question-Driven Planning - AI tendency to guess instead of investigate
- Uncertainty Tracking - preserve context across sessions

**Add these when needed (more setup):**
- Acceptance-Gate-Driven Development - comprehensive meta-process for verified progress, preventing AI drift/cheating
- ADR - when architectural decisions need to be preserved long-term
- Phased ADR Pattern - when building simpler first but preserving full design vision
- Documentation Graph - when you need to trace ADR → target → current → code
- Plan Workflow - for larger acceptance gates with multiple steps
- Claim System - for explicit parallel work coordination
- Verification Enforcement - when plans need proof of completion
- Conceptual Modeling - when AI instances repeatedly misunderstand core concepts

## Pattern Template

When adding new patterns, follow this structure:

```markdown
# Pattern: [Name]

## Problem
What goes wrong without this?

## Solution
How does this pattern solve it?

## Files
| File | Purpose |
|------|---------|
| ... | ... |

## Setup
Steps to add to a new project.

## Usage
Day-to-day commands.

## Customization
What to change for different projects.

## Limitations
What this pattern doesn't solve.
```

## Archive

Deprecated patterns are in `archive/`:
- `handoff-protocol.md` - Superseded by automatic context compaction

## Origin

These patterns emerged from the [agent_ecology](https://github.com/BrianMills2718/agent_ecology2) project while coordinating multiple Claude Code instances on a shared codebase.
