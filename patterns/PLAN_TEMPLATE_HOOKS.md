# Plan: Meta-Template Enforcement Hooks

**Status:** ✅ Complete
**Created:** 2026-01-17
**Part of:** Meta-Process Template v0.1

---

## Problem Statement

The meta-process template defines enforcement mechanisms (file scope checking, references reviewed validation, code map validation) but the hooks to implement them don't exist yet. Without these hooks, the enforcement is aspirational rather than actual.

CC instances will bypass the intended process unless hooks actively block non-compliant actions.

---

## References Reviewed

- `.claude/hooks/protect-main.sh` - existing hook pattern for blocking edits
- `.claude/hooks/block-worktree-remove.sh` - existing hook pattern for bash commands
- `.claude/settings.json` - hook configuration structure
- `docs/meta/META_TEMPLATE_SPEC_V0.1.md:449-480` - hooks specification
- `scripts/check_claims.py` - existing claims checking logic
- `docs/plans/TEMPLATE.md` - plan template format (for parsing)

---

## Files Affected

### Create
- `.claude/hooks/check-file-scope.sh` - Block edits to undeclared files
- `.claude/hooks/check-references-reviewed.sh` - Warn on missing exploration
- `.claude/hooks/validate-code-map.py` - CI script to validate CLAUDE.md accuracy
- `scripts/parse_plan.py` - Utility to parse plan files (Files Affected, References)

### Modify
- `.claude/settings.json` - Add new hooks to PreToolUse configuration
- `docs/plans/TEMPLATE.md` - Add References Reviewed section
- `CLAUDE.md` - Add Code Map section (if not present)
- `.github/workflows/ci.yml` - Add validate-code-map step

---

## Acceptance Criteria

- [ ] `check-file-scope.sh` blocks edits to files not in active plan's Files Affected
- [ ] `check-file-scope.sh` allows edits if file is in Files Affected list
- [ ] `check-file-scope.sh` allows edits with (create) flag for new files
- [ ] `check-references-reviewed.sh` warns if plan lacks References Reviewed section
- [ ] `check-references-reviewed.sh` warns if References Reviewed has < 2 entries
- [ ] `validate-code-map.py` reports files in Code Map that don't exist
- [ ] `validate-code-map.py` optionally reports src files not in Code Map
- [ ] All hooks have clear error messages explaining what to do
- [ ] Hooks don't block [Trivial] commits (those don't need plans)

---

## Plan

### Phase 1: Plan Parsing Utility
1. Create `scripts/parse_plan.py` that can:
   - Find active plan from worktree name or claims
   - Extract Files Affected section
   - Extract References Reviewed section
   - Return structured data for hooks to use

### Phase 2: File Scope Hook
1. Create `check-file-scope.sh`
2. Hook receives file path being edited
3. Calls parse_plan.py to get Files Affected
4. Compares edit target to allowed files
5. Blocks with clear message if not in scope
6. Test with real edits

### Phase 3: References Reviewed Hook
1. Create `check-references-reviewed.sh`
2. On first edit in a session, check plan has References Reviewed
3. Warn (not block) if missing or sparse
4. Only warn once per session (avoid spam)

### Phase 4: Code Map Validation
1. Create `validate-code-map.py`
2. Parse CLAUDE.md Code Map table
3. Verify each referenced file/directory exists
4. Add to CI workflow
5. Create report of coverage gaps

### Phase 5: Integration
1. Update `.claude/settings.json` with new hooks
2. Update plan TEMPLATE.md with References Reviewed
3. Add Code Map to root CLAUDE.md if missing
4. Test full workflow end-to-end

---

## Required Tests

- `test_parse_plan_files_affected`: Extracts Files Affected correctly
- `test_parse_plan_references_reviewed`: Extracts References Reviewed correctly
- `test_check_file_scope_allows_declared`: Hook allows declared files
- `test_check_file_scope_blocks_undeclared`: Hook blocks undeclared files
- `test_check_file_scope_allows_create`: Hook allows (create) files
- `test_validate_code_map_finds_stale`: Finds non-existent files in map
- `test_validate_code_map_finds_missing`: Finds undocumented src files

---

## Dependencies

- Existing hook infrastructure (`.claude/hooks/`, settings.json)
- Plan template format (for parsing)
- Claims system (to identify active plan)

---

## Risks

| Risk | Mitigation |
|------|------------|
| Hook too strict, blocks legitimate work | Clear escape hatch: update plan first |
| Plan parsing fragile | Use robust regex, test edge cases |
| Performance impact (hook on every edit) | Cache plan parsing per session |

---

## Verification Evidence

<!-- To be filled on completion -->
