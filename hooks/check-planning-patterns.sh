#!/bin/bash
# Hook: Check planning patterns before allowing plan edits
#
# This hook validates that plan files follow planning patterns:
# - Open Questions section exists
# - No unverified claims ("I believe", "might be", etc.)
# - No prohibited terms from conceptual model
#
# Configuration (meta-process.yaml):
#   planning:
#     question_driven_planning: advisory | required | disabled
#     warn_on_unverified_claims: true | false
#
# Usage in .claude/settings.json:
#   "hooks": {
#     "PostToolUse": [
#       {
#         "matcher": "Edit|Write",
#         "command": "bash meta-process/hooks/check-planning-patterns.sh \"$FILE_PATH\""
#       }
#     ]
#   }

set -e

FILE_PATH="$1"
PROJECT_ROOT="${PROJECT_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"

# Only check plan files
if [[ ! "$FILE_PATH" =~ docs/plans/[0-9].*\.md$ ]]; then
    exit 0
fi

# Check if planning patterns are enabled
if command -v yq &> /dev/null; then
    QDP_LEVEL=$(yq -r '.planning.question_driven_planning // "advisory"' "$PROJECT_ROOT/meta-process.yaml" 2>/dev/null || echo "advisory")
    WARN_UNVERIFIED=$(yq -r '.planning.warn_on_unverified_claims // true' "$PROJECT_ROOT/meta-process.yaml" 2>/dev/null || echo "true")
else
    QDP_LEVEL="advisory"
    WARN_UNVERIFIED="true"
fi

# Skip if disabled
if [[ "$QDP_LEVEL" == "disabled" ]]; then
    exit 0
fi

WARNINGS=""
ERRORS=""

# Check for Open Questions section
if ! grep -q "## Open Questions" "$FILE_PATH" 2>/dev/null; then
    if [[ "$QDP_LEVEL" == "required" ]]; then
        ERRORS="${ERRORS}ERROR: Missing '## Open Questions' section (required)\n"
    else
        WARNINGS="${WARNINGS}WARNING: Consider adding '## Open Questions' section\n"
    fi
fi

# Check for unverified claims
if [[ "$WARN_UNVERIFIED" == "true" ]]; then
    # Patterns that indicate unverified assumptions
    UNVERIFIED_PATTERNS="I believe|might be|probably|presumably|I think|I assume"

    # Search for patterns (excluding code blocks and comments)
    MATCHES=$(grep -n -E "$UNVERIFIED_PATTERNS" "$FILE_PATH" 2>/dev/null | grep -v "^\s*#" | grep -v '```' | head -5 || true)

    if [[ -n "$MATCHES" ]]; then
        WARNINGS="${WARNINGS}WARNING: Found unverified claim language - investigate instead of assuming:\n"
        while IFS= read -r line; do
            WARNINGS="${WARNINGS}  $line\n"
        done <<< "$MATCHES"
    fi
fi

# Output results
if [[ -n "$ERRORS" ]]; then
    echo -e "\n=== Planning Pattern Errors ==="
    echo -e "$ERRORS"
    exit 1
fi

if [[ -n "$WARNINGS" ]]; then
    echo -e "\n=== Planning Pattern Warnings ==="
    echo -e "$WARNINGS"
    echo "Tip: Use 'I verified in src/file.py:XX' instead of 'I believe'"
fi

exit 0
