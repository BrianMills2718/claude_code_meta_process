# Gap N: [Name]

**Status:** ❌ Needs Plan
**Priority:** High | Medium | Low
**Blocked By:** #X, #Y
**Blocks:** #A, #B

---

## Gap

**Current:** What exists now

**Target:** What we want

**Why [Priority]:** Why this priority level

---

## References Reviewed

**Required:** Document what code/docs you reviewed before planning.
This forces exploration before implementation and creates traceability.

- `src/relevant/file.py:10-50` - description of what you learned
- `docs/architecture/current/relevant.md` - relevant design context
- `CLAUDE.md` - project conventions reviewed

---

## Open Questions

**Required:** List unknowns BEFORE proposing solutions.
Investigate each question - don't guess. See [Question-Driven Planning](../../meta-process/patterns/28_question-driven-planning.md).

### Before Planning

<!-- List questions that must be answered before you can plan -->

1. [ ] **Question:** [What do you need to know?]
   - **Status:** ❓ OPEN
   - **Why it matters:** [Why this affects the plan]

2. [ ] **Question:** [Another unknown]
   - **Status:** ❓ OPEN
   - **Why it matters:** [Impact on design]

### Resolved

<!-- Move questions here after INVESTIGATING (not guessing!) -->

1. [x] **Question:** [Example resolved question]
   - **Status:** ✅ RESOLVED
   - **Answer:** [What you found by reading code/docs]
   - **Verified in:** `src/path/file.py:45-60`

---

## Files Affected

**Required:** Declare what files will be touched. Hook blocks undeclared edits.

- `src/path/to/file.py` (modify)
- `src/path/to/new_file.py` (create)
- `tests/test_feature.py` (create)

---

## Plan

### Changes Required
| File | Change |
|------|--------|
| ... | ... |

### Steps
1. Step one
2. Step two

---

## Required Tests

### New Tests (TDD)

Create these tests FIRST, before implementing:

| Test File | Test Function | What It Verifies |
|-----------|---------------|------------------|
| `tests/test_feature.py` | `test_happy_path` | Basic functionality works |
| `tests/test_feature.py` | `test_edge_case` | Handles edge case |

### Existing Tests (Must Pass)

These tests must still pass after changes:

| Test Pattern | Why |
|--------------|-----|
| `tests/test_related.py` | Integration unchanged |
| `tests/test_other.py::test_specific` | Specific behavior preserved |

---

## E2E Verification

**Required:** Every feature must work end-to-end with real LLM before completion.

| Scenario | Steps | Expected Outcome |
|----------|-------|------------------|
| [Describe E2E scenario] | 1. Run simulation with feature enabled 2. ... | [What should happen] |

```bash
# Run E2E verification
pytest tests/e2e/test_real_e2e.py -v --run-external
```

---

## Verification

### Tests & Quality
- [ ] All required tests pass: `python scripts/check_plan_tests.py --plan N`
- [ ] Full test suite passes: `pytest tests/`
- [ ] Type check passes: `python -m mypy src/ --ignore-missing-imports`
- [ ] **E2E verification passes:** `pytest tests/e2e/test_real_e2e.py -v --run-external`

### Documentation
- [ ] `docs/architecture/current/` updated
- [ ] Doc-coupling check passes: `python scripts/check_doc_coupling.py`
- [ ] [Plan-specific criteria]

### Completion Ceremony
- [ ] Plan file status → `✅ Complete`
- [ ] `plans/CLAUDE.md` index → `✅ Complete`
- [ ] Claim released from Active Work table (root CLAUDE.md)
- [ ] Branch merged or PR created

---

## Uncertainties

Track uncertainties discovered during implementation.
See [Uncertainty Tracking](../../meta-process/patterns/29_uncertainty-tracking.md).

| Question | Status | Resolution |
|----------|--------|------------|
| [Uncertainty discovered during work] | ❓ Open | - |
| [Example resolved] | ✅ Resolved | [What was decided and why] |
| [Example deferred] | ⏸️ Deferred | [Accepted risk: ...] |

**Status key:** ❓ Open | 🔍 Investigating | ✅ Resolved | ⏸️ Deferred | 🚫 Blocked

---

## Notes
[Design decisions, alternatives considered, etc.]
