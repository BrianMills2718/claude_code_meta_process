# Claude Code Meta-Process

**Planning is the leverage point.**

Claude Code works well on small projects. On large or complex codebases, it struggles—making no progress, or introducing regressions. The difference isn't the model. It's whether you planned before executing.

This framework provides a structured planning process that Claude Code walks you through, then enforces during implementation.

## The Planning Process

Before writing code, establish context and direction:

```
PRD → Conceptual Model → Architecture → Gaps → Plans → Implementation
```

### 1. PRD (Product Requirements)

Start with what you're trying to achieve. What problem are you solving? What does success look like?

```markdown
## Problem
Users can't recover their account if they lose their password.

## Requirements
- User can request password reset via email
- Reset link expires after 24 hours
- User must create new password meeting security requirements

## Success Criteria
- User can regain access within 5 minutes
- No support tickets for password reset
```

### 2. Conceptual Model

Define what things ARE in your system. This prevents Claude Code from misunderstanding your architecture.

```yaml
# docs/CONCEPTUAL_MODEL.yaml
concepts:
  user:
    definition: "A person with an account"
    properties: [id, email, password_hash, created_at]

  session:
    definition: "An authenticated user's active login"
    properties: [token, user_id, expires_at]

  reset_token:
    definition: "One-time token for password recovery"
    properties: [token, user_id, expires_at, used]

relationships:
  - user has_many sessions
  - user has_many reset_tokens
```

### 3. Architecture Documentation

Document what exists (current) and where you're headed (target).

```
docs/architecture/
├── current/          # What IS implemented
│   ├── auth.md       # Current auth system
│   └── database.md   # Current schema
├── target/           # What we WANT
│   └── auth.md       # Target auth with password reset
└── adr/              # Architecture Decision Records
    └── 001-jwt-sessions.md
```

**ADRs** capture decisions and their rationale:

```markdown
# ADR-001: Use JWT for Sessions

## Status
Accepted

## Context
Need stateless authentication for horizontal scaling.

## Decision
Use JWT tokens stored in httpOnly cookies.

## Consequences
- Stateless: no session store needed
- Can't invalidate tokens server-side without blacklist
```

### 4. Gap Analysis

Identify the delta between current and target:

```markdown
# Gap: Password Reset

**Current:** No password recovery mechanism
**Target:** Email-based password reset with expiring tokens
**Priority:** High (blocking user acquisition)
**Blocked by:** None
**Blocks:** User onboarding flow
```

### 5. Plan

For each gap, create a plan with:

```markdown
# Plan 12: Password Reset

## Open Questions (Investigate BEFORE planning)

1. [x] Where is auth currently handled?
   - Resolved: src/auth/login.py handles all auth

2. [x] How are emails sent?
   - Resolved: src/notifications/email.py, uses SendGrid

3. [ ] What's the password policy?
   - Status: OPEN - need to check with product

## References Reviewed

- `src/auth/login.py:45-120` - current auth flow
- `src/models/user.py` - user model
- `docs/architecture/current/auth.md` - auth design

## Files Affected

- `src/auth/reset.py` (create)
- `src/models/reset_token.py` (create)
- `src/auth/login.py` (modify)
- `tests/test_password_reset.py` (create)

## Implementation Steps

1. Create ResetToken model
2. Add reset request endpoint
3. Add reset confirmation endpoint
4. Send reset email
5. Update login to check for required reset

## Required Tests (TDD)

Write these FIRST:

| Test | Verifies |
|------|----------|
| `test_request_reset_sends_email` | Email sent with valid token |
| `test_reset_token_expires` | Can't use expired token |
| `test_reset_changes_password` | Password actually changes |
| `test_reset_invalidates_token` | Token can't be reused |

## E2E Verification

Before marking complete:
- [ ] Request reset for real email
- [ ] Click link, reset password
- [ ] Login with new password
- [ ] Verify old password rejected
```

### 6. Implementation with Enforcement

Plans are enforced during implementation:

- **TDD**: Tests must exist before implementation code
- **Scope enforcement**: Can only edit files declared in plan
- **E2E requirement**: Must pass real E2E test before "complete"
- **Uncertainty tracking**: New questions get logged, not guessed

## Enforcement Configuration

```yaml
# meta-process.yaml
planning:
  question_driven_planning: required   # Must resolve questions first
  uncertainty_tracking: advisory       # Track unknowns
  warn_on_unverified_claims: true      # Flag "I believe", "probably"

testing:
  require_tests_before_implementation: true  # TDD
  require_e2e_before_complete: true          # Real E2E required
```

## What's Included

| Directory | Purpose |
|-----------|---------|
| `patterns/` | 29 patterns for planning, testing, coordination |
| `templates/` | Plan template, ADR template, PRD template |
| `hooks/` | Enforcement hooks for Git and Claude Code |
| `scripts/` | Validation and enforcement scripts |

## Key Patterns

| Pattern | Purpose |
|---------|---------|
| [Question-Driven Planning](patterns/28_question-driven-planning.md) | Investigate before assuming |
| [Uncertainty Tracking](patterns/29_uncertainty-tracking.md) | Preserve context across sessions |
| [Conceptual Modeling](patterns/27_conceptual-modeling.md) | Define what things ARE |
| [ADR](patterns/07_adr.md) | Capture architectural decisions |
| [Plan Workflow](patterns/15_plan-workflow.md) | Structure implementation work |
| [Acceptance-Gate-Driven Development](patterns/13_acceptance-gate-driven-development.md) | E2E verification checkpoints |

## Documentation

- [Getting Started](GETTING_STARTED.md) - Adoption guide
- [All Patterns](patterns/01_README.md) - Full pattern index
- [Hooks](hooks/README.md) - Enforcement hooks
