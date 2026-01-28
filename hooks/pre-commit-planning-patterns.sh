#!/bin/bash
# Pre-commit hook: Validate planning patterns in changed plan files
#
# Add to your pre-commit hook chain:
#   source meta-process/hooks/pre-commit-planning-patterns.sh
#
# Or call directly:
#   bash meta-process/hooks/pre-commit-planning-patterns.sh
#
# Configuration (meta-process.yaml):
#   planning:
#     question_driven_planning: advisory | required | disabled
#     uncertainty_tracking: advisory | required | disabled

set -e

PROJECT_ROOT="${PROJECT_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"

# Get changed plan files in staging
CHANGED_PLANS=$(git diff --cached --name-only --diff-filter=ACM | grep -E '^docs/plans/[0-9].*\.md$' || true)

if [[ -z "$CHANGED_PLANS" ]]; then
    exit 0
fi

echo "Checking planning patterns in modified plans..."

# Check if the script exists
SCRIPT="$PROJECT_ROOT/scripts/check_planning_patterns.py"
if [[ ! -f "$SCRIPT" ]]; then
    echo "WARNING: check_planning_patterns.py not found, skipping planning pattern validation"
    exit 0
fi

# Run validation on each changed plan
FAILED=0
for plan in $CHANGED_PLANS; do
    if ! python "$SCRIPT" --file "$PROJECT_ROOT/$plan" --project-root "$PROJECT_ROOT"; then
        FAILED=1
    fi
done

if [[ $FAILED -eq 1 ]]; then
    echo ""
    echo "Planning pattern validation failed."
    echo "Fix the errors above or use --no-verify to skip (not recommended)."
    echo ""
    echo "To check a specific plan:"
    echo "  python scripts/check_planning_patterns.py --plan N"
    echo ""
    exit 1
fi

echo "Planning patterns OK"
exit 0
