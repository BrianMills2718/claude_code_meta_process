#!/usr/bin/env python3
"""
Validate planning patterns in plan files.

Checks:
1. Open Questions section exists and questions are resolved (if required)
2. Uncertainties section exists (if required)
3. No unverified claims ("I believe", "might be", etc.)
4. No prohibited terms from conceptual model

Configuration via meta-process.yaml:
  planning:
    question_driven_planning: advisory | required | disabled
    uncertainty_tracking: advisory | required | disabled
    warn_on_unverified_claims: true | false
    warn_on_prohibited_terms: true | false
    conceptual_model_path: docs/CONCEPTUAL_MODEL.yaml

Usage:
    python scripts/check_planning_patterns.py --plan 229
    python scripts/check_planning_patterns.py --all
    python scripts/check_planning_patterns.py --plan 229 --strict
    python scripts/check_planning_patterns.py --file path/to/plan.md
"""

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

import yaml


class Issue(NamedTuple):
    """A validation issue."""
    level: str  # "error" | "warning"
    message: str
    line: int | None = None


class ValidationResult(NamedTuple):
    """Result of validating a plan file."""
    path: Path
    issues: list[Issue]

    @property
    def has_errors(self) -> bool:
        return any(i.level == "error" for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.level == "warning" for i in self.issues)


def load_config(project_root: Path) -> dict:
    """Load meta-process.yaml configuration."""
    config_path = project_root / "meta-process.yaml"
    if not config_path.exists():
        return {}

    with open(config_path) as f:
        config = yaml.safe_load(f) or {}

    return config.get("planning", {})


def load_conceptual_model(project_root: Path, config: dict) -> dict:
    """Load conceptual model if it exists."""
    model_path = config.get("conceptual_model_path", "docs/CONCEPTUAL_MODEL.yaml")
    full_path = project_root / model_path

    if not full_path.exists():
        return {}

    with open(full_path) as f:
        return yaml.safe_load(f) or {}


def get_prohibited_terms(model: dict) -> list[str]:
    """Extract prohibited terms from conceptual model."""
    non_existence = model.get("non_existence", {})
    if isinstance(non_existence, dict):
        return list(non_existence.keys())
    return []


# Patterns that indicate unverified claims
UNVERIFIED_PATTERNS = [
    (r"\bI believe\b", "I believe"),
    (r"\bmight be\b", "might be"),
    (r"\bprobably\b", "probably"),
    (r"\bpresumably\b", "presumably"),
    (r"\bI think\b", "I think"),
    (r"\bI assume\b", "I assume"),
    (r"\bshould be\b", "should be"),  # In planning context, often indicates uncertainty
    (r"\blikely\b", "likely"),
    (r"\bpossibly\b", "possibly"),
]


def check_open_questions_section(content: str, lines: list[str], level: str) -> list[Issue]:
    """Check Open Questions section exists and is properly filled."""
    issues = []

    if level == "disabled":
        return issues

    # Check section exists
    if "## Open Questions" not in content:
        issue_level = "error" if level == "required" else "warning"
        issues.append(Issue(issue_level, "Missing '## Open Questions' section"))
        return issues

    # Find the section
    in_section = False
    in_before_planning = False
    open_questions = []

    for i, line in enumerate(lines, 1):
        if "## Open Questions" in line:
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and "### Before Planning" in line:
            in_before_planning = True
            continue
        if in_section and "### Resolved" in line:
            in_before_planning = False
            continue

        # Look for unresolved questions in Before Planning
        if in_before_planning:
            # Match unchecked checkbox with question
            if re.match(r"\s*\d+\.\s*\[ \]", line):
                open_questions.append((i, line.strip()))

    # If there are unresolved questions and level is required, that's an error
    if open_questions and level == "required":
        for line_num, question in open_questions:
            issues.append(Issue(
                "error",
                f"Unresolved question (required level): {question[:50]}...",
                line_num
            ))
    elif open_questions and level == "advisory":
        # Just informational - open questions exist
        pass

    return issues


def check_uncertainties_section(content: str, lines: list[str], level: str) -> list[Issue]:
    """Check Uncertainties section exists."""
    issues = []

    if level == "disabled":
        return issues

    if "## Uncertainties" not in content:
        issue_level = "error" if level == "required" else "warning"
        issues.append(Issue(issue_level, "Missing '## Uncertainties' section"))

    return issues


def check_unverified_claims(content: str, lines: list[str], enabled: bool) -> list[Issue]:
    """Check for unverified claim language."""
    issues = []

    if not enabled:
        return issues

    # Skip checking in certain sections (like examples or templates)
    skip_sections = ["## Notes", "## References"]
    in_skip_section = False

    for i, line in enumerate(lines, 1):
        # Track sections to skip
        if any(section in line for section in skip_sections):
            in_skip_section = True
        elif line.startswith("## "):
            in_skip_section = False

        if in_skip_section:
            continue

        # Skip code blocks
        if line.strip().startswith("```") or line.strip().startswith("`"):
            continue

        # Skip lines that are clearly examples or templates
        if "[" in line and "]" in line and line.strip().startswith("-"):
            continue

        for pattern, term in UNVERIFIED_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                issues.append(Issue(
                    "warning",
                    f"Unverified claim language '{term}' - investigate instead of assuming",
                    i
                ))
                break  # One warning per line

    return issues


def check_prohibited_terms(content: str, lines: list[str], terms: list[str], enabled: bool) -> list[Issue]:
    """Check for terms that should not be used."""
    issues = []

    if not enabled or not terms:
        return issues

    for i, line in enumerate(lines, 1):
        # Skip code blocks and comments
        if line.strip().startswith("```") or line.strip().startswith("#"):
            continue

        for term in terms:
            # Case-insensitive word boundary match
            pattern = rf"\b{re.escape(term)}\b"
            if re.search(pattern, line, re.IGNORECASE):
                issues.append(Issue(
                    "warning",
                    f"Prohibited term '{term}' - see conceptual model non_existence section",
                    i
                ))

    return issues


def validate_plan(plan_path: Path, config: dict, model: dict, strict: bool = False) -> ValidationResult:
    """Validate a single plan file."""
    issues = []

    if not plan_path.exists():
        return ValidationResult(plan_path, [Issue("error", "Plan file does not exist")])

    content = plan_path.read_text()
    lines = content.split("\n")

    # Get configuration levels
    qdp_level = config.get("question_driven_planning", "advisory")
    ut_level = config.get("uncertainty_tracking", "advisory")
    warn_unverified = config.get("warn_on_unverified_claims", True)
    warn_prohibited = config.get("warn_on_prohibited_terms", True)

    # Override to required if strict mode
    if strict:
        if qdp_level != "disabled":
            qdp_level = "required"
        if ut_level != "disabled":
            ut_level = "required"

    # Run checks
    issues.extend(check_open_questions_section(content, lines, qdp_level))
    issues.extend(check_uncertainties_section(content, lines, ut_level))
    issues.extend(check_unverified_claims(content, lines, warn_unverified))

    prohibited_terms = get_prohibited_terms(model)
    issues.extend(check_prohibited_terms(content, lines, prohibited_terms, warn_prohibited))

    return ValidationResult(plan_path, issues)


def find_plan_file(project_root: Path, plan_num: int) -> Path | None:
    """Find plan file by number."""
    plans_dir = project_root / "docs" / "plans"

    # Try different patterns
    patterns = [
        f"{plan_num}_*.md",
        f"{plan_num:02d}_*.md",
        f"{plan_num:03d}_*.md",
    ]

    for pattern in patterns:
        matches = list(plans_dir.glob(pattern))
        if matches:
            return matches[0]

    return None


def find_all_plans(project_root: Path) -> list[Path]:
    """Find all plan files."""
    plans_dir = project_root / "docs" / "plans"

    # Match numbered plan files, exclude TEMPLATE and CLAUDE.md
    plans = []
    for f in plans_dir.glob("*.md"):
        if f.name in ("TEMPLATE.md", "CLAUDE.md"):
            continue
        # Must start with a number
        if f.name[0].isdigit():
            plans.append(f)

    return sorted(plans)


def print_result(result: ValidationResult, verbose: bool = False) -> None:
    """Print validation result."""
    if not result.issues:
        if verbose:
            print(f"  {result.path.name}: OK")
        return

    print(f"\n{result.path.name}:")
    for issue in result.issues:
        prefix = "  ERROR:" if issue.level == "error" else "  WARNING:"
        line_info = f" (line {issue.line})" if issue.line else ""
        print(f"{prefix}{line_info} {issue.message}")


def main():
    parser = argparse.ArgumentParser(description="Validate planning patterns in plan files")
    parser.add_argument("--plan", type=int, help="Plan number to check")
    parser.add_argument("--file", type=Path, help="Specific file to check")
    parser.add_argument("--all", action="store_true", help="Check all plan files")
    parser.add_argument("--strict", action="store_true", help="Treat advisory as required")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all results")
    parser.add_argument("--project-root", type=Path, default=Path.cwd(), help="Project root")

    args = parser.parse_args()

    if not any([args.plan, args.file, args.all]):
        parser.error("Must specify --plan N, --file PATH, or --all")

    project_root = args.project_root
    config = load_config(project_root)
    model = load_conceptual_model(project_root, config)

    # Collect files to check
    files_to_check = []

    if args.file:
        files_to_check.append(args.file)
    elif args.plan:
        plan_path = find_plan_file(project_root, args.plan)
        if not plan_path:
            print(f"ERROR: Plan {args.plan} not found")
            sys.exit(1)
        files_to_check.append(plan_path)
    elif args.all:
        files_to_check = find_all_plans(project_root)

    if not files_to_check:
        print("No plan files found")
        sys.exit(0)

    # Validate
    results = []
    for path in files_to_check:
        result = validate_plan(path, config, model, strict=args.strict)
        results.append(result)
        print_result(result, verbose=args.verbose)

    # Summary
    total_errors = sum(1 for r in results if r.has_errors)
    total_warnings = sum(1 for r in results if r.has_warnings and not r.has_errors)

    print(f"\n--- Summary ---")
    print(f"Files checked: {len(results)}")
    print(f"Errors: {total_errors}")
    print(f"Warnings: {total_warnings}")

    if total_errors > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
