# Claude Code Meta-Process

**Planning is the leverage point.**

Claude Code works well on small projects. On large or complex codebases, it struggles—making no progress, or introducing regressions. The difference isn't the model. It's whether you planned before executing.

This framework provides structured planning that Claude Code walks you through, then enforces during implementation.

## The Problem

Without structured planning on complex repos:
- Claude Code guesses instead of investigating
- Assumptions collapse late in implementation
- Context is lost across sessions
- Work thrashes or breaks existing functionality

## The Solution

Plan first. Enforce the plan during execution.

1. **Surface questions before proposing solutions** - Investigate, don't assume
2. **Track uncertainties explicitly** - Preserve context across sessions
3. **Verify claims in code** - Every "I believe" becomes "I verified in X"
4. **Enforce plans with hooks** - Catch drift before it causes damage

## Core Planning Patterns

### Question-Driven Planning

Before writing code, list what you don't know. Investigate each question.

```markdown
## Open Questions

1. [ ] Where does permission checking happen?
   - Status: OPEN
   - Why it matters: Need to understand before modifying

2. [x] How are contracts validated?
   - Status: RESOLVED
   - Answer: In permission_checker.py:34-89
   - Verified in: src/world/permission_checker.py
```

### Uncertainty Tracking

Track what's unknown, what's being investigated, what's resolved.

```markdown
| Question | Status | Resolution |
|----------|--------|------------|
| Contract validation? | ✅ Resolved | src/contracts.py:45-80 |
| Default behavior? | 🔍 Investigating | Checking genesis... |
| Edge case X? | ⏸️ Deferred | Out of scope, accepted risk |
```

### Don't Guess, Verify

Hooks warn when plans contain unverified language ("I believe", "probably", "should be").

## Enforcement

Configure how strictly planning is enforced:

```yaml
# meta-process.yaml
planning:
  question_driven_planning: advisory  # disabled | advisory | required
  uncertainty_tracking: advisory
  warn_on_unverified_claims: true
```

| Level | Behavior |
|-------|----------|
| `disabled` | No checks |
| `advisory` | Warnings (default) |
| `required` | Blocks until resolved |

## Getting Started

```bash
# Copy planning patterns and templates to your project
cp -r patterns/ your-project/meta-process/patterns/
cp templates/PLAN_TEMPLATE.md your-project/docs/plans/TEMPLATE.md
cp meta-process.yaml.example your-project/meta-process.yaml

# Before starting any significant work:
# 1. Create a plan from the template
# 2. Fill in Open Questions - investigate each one
# 3. List files you'll touch
# 4. Then implement
```

## What's Included

```
├── patterns/           # 29 patterns (planning, coordination, quality)
├── templates/          # Plan template with required sections
├── hooks/              # Enforcement for Git and Claude Code
├── scripts/            # Validation scripts
└── meta-process.yaml   # Configuration
```

## Key Patterns

| Pattern | Problem It Solves |
|---------|-------------------|
| [Question-Driven Planning](patterns/28_question-driven-planning.md) | Guessing instead of investigating |
| [Uncertainty Tracking](patterns/29_uncertainty-tracking.md) | Losing context across sessions |
| [Plan Workflow](patterns/15_plan-workflow.md) | Scope creep, untracked changes |
| [Conceptual Modeling](patterns/27_conceptual-modeling.md) | Repeated misunderstandings of architecture |

## Documentation

- [Getting Started](GETTING_STARTED.md) - Adoption guide
- [All Patterns](patterns/01_README.md) - Full pattern index
- [Hooks](hooks/README.md) - Enforcement hooks

## Origin

Built while running multiple Claude Code instances on a 200+ file codebase. Without structured planning, results were inconsistent. With it, Claude Code became reliable on complex work.
