#!/usr/bin/env python3
"""Check that documentation is updated when coupled source files change.

Usage:
    python scripts/check_doc_coupling.py [--base BASE_REF] [--suggest]
    python scripts/check_doc_coupling.py --staged  # For pre-commit hook
    python scripts/check_doc_coupling.py --bidirectional  # Check both directions
    python scripts/check_doc_coupling.py --suggest-all FILE  # Show all relationships

Compares current branch against BASE_REF (default: origin/main) to find
changed files, then checks if coupled docs were also updated.

The --staged option checks only staged files, suitable for pre-commit hooks.
If source files are staged AND their coupled docs are also staged, it passes.

Bidirectional mode (Plan #216):
- Code changes → surface related docs + ADRs
- Doc changes → surface related code + ADRs
- ADR changes → surface governed code + related docs

Exit codes:
    0 - All couplings satisfied (or no coupled changes)
    1 - Missing doc updates (strict violations)
"""

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

# Plan #218: Weight-aware check control
try:
    from meta_process_config import Weight, check_enabled
    HAS_WEIGHT_CONFIG = True
except ImportError:
    HAS_WEIGHT_CONFIG = False


META_CONFIG_FILE = Path("meta-process.yaml")
RELATIONSHIPS_FILE = Path("scripts/relationships.yaml")


def load_meta_config() -> dict:
    """Load meta-process configuration.

    Returns default values if config file doesn't exist.
    """
    defaults = {
        "enforcement": {
            "plan_index_auto_add": True,
            "strict_doc_coupling": True,
            "show_strictness_warning": True,
        }
    }

    if not META_CONFIG_FILE.exists():
        return defaults

    try:
        with open(META_CONFIG_FILE) as f:
            config = yaml.safe_load(f) or {}
        # Merge with defaults
        enforcement = defaults["enforcement"].copy()
        enforcement.update(config.get("enforcement", {}))
        return {"enforcement": enforcement}
    except Exception:
        return defaults


def get_changed_files(base_ref: str) -> set[str]:
    """Get files changed between base_ref and HEAD."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base_ref, "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return set(result.stdout.strip().split("\n")) - {""}
    except subprocess.CalledProcessError:
        # Fallback: compare against HEAD~1 for local testing
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            return set(result.stdout.strip().split("\n")) - {""}
        except subprocess.CalledProcessError:
            return set()


def get_staged_files() -> set[str]:
    """Get files staged for commit."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
        )
        return set(result.stdout.strip().split("\n")) - {""}
    except subprocess.CalledProcessError:
        return set()


def load_couplings(config_path: Path) -> list[dict]:
    """Load coupling definitions from YAML.

    Supports both formats:
    - relationships.yaml (unified): has 'couplings' section with full paths
    - doc_coupling.yaml (legacy): has 'couplings' section with full paths

    If config_path is doc_coupling.yaml but relationships.yaml exists and has
    couplings, prefer relationships.yaml (unified source of truth).
    """
    # Check if we should use relationships.yaml instead
    relationships_path = config_path.parent / "relationships.yaml"
    if config_path.name == "doc_coupling.yaml" and relationships_path.exists():
        with open(relationships_path) as f:
            unified_data = yaml.safe_load(f)
        if unified_data and "couplings" in unified_data:
            # Use unified relationships.yaml
            return unified_data.get("couplings", [])

    # Fall back to specified config file
    with open(config_path) as f:
        data = yaml.safe_load(f)
    return data.get("couplings", [])


def load_relationships(config_path: Path | None = None) -> dict[str, Any]:
    """Load full relationships from YAML.

    Args:
        config_path: Path to relationships.yaml, or None to use default.

    Returns:
        Dict with 'adrs', 'governance', and 'couplings' sections.
    """
    path = config_path or RELATIONSHIPS_FILE
    if not path.exists():
        return {"adrs": {}, "governance": [], "couplings": []}

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    return {
        "adrs": data.get("adrs", {}),
        "governance": data.get("governance", []),
        "couplings": data.get("couplings", []),
    }


def extract_adr_number(filepath: Path) -> int | None:
    """Extract ADR number from an ADR file path.

    Args:
        filepath: Path like 'docs/adr/0003-contracts-can-do-anything.md'

    Returns:
        ADR number (e.g., 3) or None if not an ADR path.
    """
    if "docs/adr/" not in str(filepath):
        return None

    # Match pattern like 0001-xxx.md or 0003-xxx.md
    match = re.search(r"(\d{4})-[^/]+\.md$", str(filepath))
    if match:
        return int(match.group(1))
    return None


def get_related_nodes(
    changed_file: Path,
    relationships: dict[str, Any],
) -> list[str]:
    """Find all nodes related to changed_file in any direction.

    This implements bidirectional coupling: given any file, find all
    related files whether the relationship is source→doc, doc→source,
    source→ADR, or ADR→source.

    Args:
        changed_file: Path to the changed file.
        relationships: Dict from load_relationships().

    Returns:
        List of related file paths.
    """
    related: list[str] = []
    filepath = str(changed_file)

    # Check couplings (source ↔ doc, bidirectional)
    for coupling in relationships.get("couplings", []):
        sources = coupling.get("sources", [])
        docs = coupling.get("docs", [])

        # If changed file matches a source pattern, add related docs
        if matches_any_pattern(filepath, sources):
            related.extend(docs)

        # If changed file is a doc, add related sources
        if filepath in docs:
            related.extend(sources)

    # Check governance (source ↔ ADR, bidirectional)
    for entry in relationships.get("governance", []):
        source = entry.get("source", "")
        adrs = entry.get("adrs", [])

        # If changed file is a governed source, add related ADRs
        if filepath == source:
            adr_defs = relationships.get("adrs", {})
            for adr_num in adrs:
                adr_info = adr_defs.get(adr_num, {})
                adr_file = adr_info.get("file", f"{adr_num:04d}-unknown.md")
                related.append(f"docs/adr/{adr_file}")

        # If changed file is an ADR, add governed sources
        adr_num = extract_adr_number(changed_file)
        if adr_num is not None and adr_num in adrs:
            related.append(source)

    # Remove duplicates while preserving order
    seen: set[str] = set()
    unique_related: list[str] = []
    for item in related:
        if item not in seen:
            seen.add(item)
            unique_related.append(item)

    return unique_related


def get_related_nodes_with_context(
    changed_file: Path,
    relationships: dict[str, Any],
) -> dict[str, Any]:
    """Find all related nodes with governance context.

    Like get_related_nodes() but also returns governance context if available.

    Args:
        changed_file: Path to the changed file.
        relationships: Dict from load_relationships().

    Returns:
        Dict with 'related' (list of paths) and 'context' (string or None).
    """
    related = get_related_nodes(changed_file, relationships)
    context = None

    # Find governance context for this file
    filepath = str(changed_file)
    for entry in relationships.get("governance", []):
        if entry.get("source") == filepath:
            context = entry.get("context", "")
            break

    return {"related": related, "context": context}


def check_bidirectional(
    changed_files: set[str],
    relationships: dict[str, Any],
) -> list[dict[str, Any]]:
    """Check couplings bidirectionally.

    For each changed file, check if its related files were also changed.
    Returns warnings for files that might need attention.

    Args:
        changed_files: Set of changed file paths.
        relationships: Dict from load_relationships().

    Returns:
        List of warning dicts with 'changed', 'related', 'description'.
    """
    warnings: list[dict[str, Any]] = []

    for changed in changed_files:
        related = get_related_nodes(Path(changed), relationships)

        # Find which related files were NOT changed
        missing = [r for r in related if r not in changed_files]

        if missing:
            warnings.append({
                "changed": changed,
                "related": missing,
                "description": f"Consider checking: {', '.join(missing[:3])}",
            })

    return warnings


def get_suggest_all_output(
    filepath: Path,
    relationships: dict[str, Any],
) -> str:
    """Generate --suggest-all output for a file.

    Shows all relationships for the given file: ADRs, docs, and context.

    Args:
        filepath: Path to query.
        relationships: Dict from load_relationships().

    Returns:
        Formatted string for display.
    """
    lines = [f"Related to {filepath}:"]

    filepath_str = str(filepath)

    # Find ADRs that govern this file
    adrs_found: list[str] = []
    context = None
    for entry in relationships.get("governance", []):
        if entry.get("source") == filepath_str:
            adr_defs = relationships.get("adrs", {})
            for adr_num in entry.get("adrs", []):
                adr_info = adr_defs.get(adr_num, {})
                adr_file = adr_info.get("file", f"{adr_num:04d}-unknown.md")
                adr_title = adr_info.get("title", "Unknown")
                adrs_found.append(f"docs/adr/{adr_file} ({adr_title})")
            context = entry.get("context")

    # Find coupled docs
    docs_found: list[str] = []
    for coupling in relationships.get("couplings", []):
        sources = coupling.get("sources", [])
        docs = coupling.get("docs", [])
        if matches_any_pattern(filepath_str, sources):
            for doc in docs:
                desc = coupling.get("description", "")
                docs_found.append(f"{doc} ({desc})")

    # Format output
    if adrs_found:
        lines.append("  ADRs:")
        for adr in adrs_found:
            lines.append(f"    - {adr}")

    if docs_found:
        lines.append("  Docs:")
        for doc in docs_found:
            lines.append(f"    - {doc}")

    if context:
        lines.append("  Context:")
        for line in context.strip().split("\n"):
            lines.append(f"    {line}")

    if not adrs_found and not docs_found:
        lines.append("  (No relationships found)")

    return "\n".join(lines)


def validate_config(couplings: list[dict]) -> list[str]:
    """Validate that all referenced files in config exist.

    Returns list of warnings for missing files.
    """
    warnings = []
    for coupling in couplings:
        for doc in coupling.get("docs", []):
            if not Path(doc).exists():
                warnings.append(f"Coupled doc doesn't exist: {doc}")
        # Don't validate source patterns - they're globs
    return warnings


def matches_any_pattern(filepath: str, patterns: list[str]) -> bool:
    """Check if filepath matches any glob pattern."""
    for pattern in patterns:
        if fnmatch.fnmatch(filepath, pattern):
            return True
        # Also check without leading path for simple patterns
        if fnmatch.fnmatch(Path(filepath).name, pattern):
            return True
    return False


def check_couplings(
    changed_files: set[str],
    couplings: list[dict],
    force_strict: bool = False,
) -> tuple[list[dict], list[dict]]:
    """Check which couplings have source changes without doc changes.

    Args:
        changed_files: Set of changed file paths
        couplings: List of coupling definitions
        force_strict: If True, treat ALL couplings as strict (ignores soft: true)

    Returns tuple of (strict_violations, soft_warnings).
    """
    strict_violations = []
    soft_warnings = []

    for coupling in couplings:
        sources = coupling.get("sources", [])
        docs = coupling.get("docs", [])
        description = coupling.get("description", "")
        # When force_strict is True, ignore soft flag
        is_soft = coupling.get("soft", False) and not force_strict

        # Find which source patterns matched
        matched_sources = []
        for changed in changed_files:
            if matches_any_pattern(changed, sources):
                matched_sources.append(changed)

        if not matched_sources:
            continue  # No source files changed for this coupling

        # Check if any coupled doc was updated
        docs_updated = any(doc in changed_files for doc in docs)

        if not docs_updated:
            violation = {
                "description": description,
                "changed_sources": matched_sources,
                "expected_docs": docs,
                "soft": is_soft,
            }
            if is_soft:
                soft_warnings.append(violation)
            else:
                strict_violations.append(violation)

    return strict_violations, soft_warnings


def print_suggestions(changed_files: set[str], couplings: list[dict]) -> None:
    """Print which docs should be updated based on changed files."""
    print("Based on your changes, consider updating:\n")

    suggestions: dict[str, list[str]] = {}  # doc -> [reasons]

    for coupling in couplings:
        sources = coupling.get("sources", [])
        docs = coupling.get("docs", [])
        description = coupling.get("description", "")

        for changed in changed_files:
            if matches_any_pattern(changed, sources):
                for doc in docs:
                    if doc not in changed_files:
                        if doc not in suggestions:
                            suggestions[doc] = []
                        suggestions[doc].append(f"{changed} ({description})")

    if not suggestions:
        print("  No documentation updates needed.")
        return

    for doc, reasons in sorted(suggestions.items()):
        print(f"  {doc}")
        for reason in reasons[:3]:  # Limit to 3 reasons
            print(f"    <- {reason}")
        if len(reasons) > 3:
            print(f"    ... and {len(reasons) - 3} more")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check doc-code coupling")
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Base ref to compare against (default: origin/main)",
    )
    parser.add_argument(
        "--config",
        default="scripts/doc_coupling.yaml",
        help="Path to coupling config (default: scripts/doc_coupling.yaml)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error code on strict violations (default: warn only)",
    )
    parser.add_argument(
        "--suggest",
        action="store_true",
        help="Show which docs to update based on changes",
    )
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="Validate that all docs in config exist",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Check staged files only (for pre-commit hook)",
    )
    parser.add_argument(
        "--bidirectional",
        action="store_true",
        help="Check couplings in both directions (Plan #216)",
    )
    parser.add_argument(
        "--suggest-all",
        metavar="FILE",
        help="Show all relationships for a specific file",
    )
    parser.add_argument(
        "--weight-aware",
        action="store_true",
        help="Check meta-process weight before running (Plan #218)",
    )
    args = parser.parse_args()

    # Plan #218: Check if this check is enabled at current weight
    if args.weight_aware and HAS_WEIGHT_CONFIG:
        check_name = "doc_coupling_strict" if args.strict else "doc_coupling_warning"
        if not check_enabled(check_name):
            print(f"Doc coupling check ({check_name}) disabled at current weight.")
            return 0

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        return 1

    couplings = load_couplings(config_path)

    # Validate config if requested
    if args.validate_config:
        warnings = validate_config(couplings)
        if warnings:
            print("Config validation warnings:")
            for w in warnings:
                print(f"  - {w}")
            return 1
        print("Config validation passed.")
        return 0

    # --suggest-all mode: show all relationships for a file
    if args.suggest_all:
        relationships = load_relationships()
        output = get_suggest_all_output(Path(args.suggest_all), relationships)
        print(output)
        return 0

    # Get changed files based on mode
    if args.staged:
        changed_files = get_staged_files()
        if not changed_files:
            # No staged files = nothing to check
            return 0
    else:
        changed_files = get_changed_files(args.base)
        if not changed_files:
            print("No changed files detected.")
            return 0

    # Suggest mode
    if args.suggest:
        print_suggestions(changed_files, couplings)
        return 0

    # Bidirectional mode (Plan #216)
    if args.bidirectional:
        relationships = load_relationships()
        warnings = check_bidirectional(changed_files, relationships)

        if not warnings:
            print("Bidirectional coupling check passed.")
            return 0

        print("=" * 60)
        print("BIDIRECTIONAL COUPLING WARNINGS")
        print("=" * 60)
        print()
        print("The following files changed. Related files may need review:")
        print()

        for w in warnings:
            print(f"  {w['changed']}")
            for related in w["related"][:5]:
                print(f"    -> {related}")
            if len(w["related"]) > 5:
                print(f"    ... and {len(w['related']) - 5} more")
            print()

        print("=" * 60)
        print("Use --suggest-all <file> to see full relationship graph.")
        print("=" * 60)

        # Bidirectional mode is informational, don't fail
        return 0

    # Load meta-process config for strictness setting
    meta_config = load_meta_config()
    strict_doc_coupling = meta_config["enforcement"].get("strict_doc_coupling", True)
    show_warning = meta_config["enforcement"].get("show_strictness_warning", True)

    # Show warning if running in non-strict mode
    if not strict_doc_coupling and show_warning:
        print("=" * 60)
        print("WARNING: Doc-code coupling is running in NON-STRICT mode")
        print("=" * 60)
        print()
        print("Soft couplings will produce warnings instead of failures.")
        print("This allows documentation drift to accumulate silently.")
        print()
        print("To enable strict mode, set in meta-process.yaml:")
        print("  enforcement:")
        print("    strict_doc_coupling: true")
        print()
        print("=" * 60)
        print()

    strict_violations, soft_warnings = check_couplings(
        changed_files, couplings, force_strict=strict_doc_coupling
    )

    if not strict_violations and not soft_warnings:
        print("Doc-code coupling check passed.")
        return 0

    # Print violations
    if strict_violations:
        print("=" * 60)
        print("DOC-CODE COUPLING VIOLATIONS (must fix)")
        print("=" * 60)
        print()
        for v in strict_violations:
            print(f"  {v['description']}")
            print(f"    Changed: {', '.join(v['changed_sources'][:3])}")
            if len(v['changed_sources']) > 3:
                print(f"             ... and {len(v['changed_sources']) - 3} more")
            print(f"    Update:  {', '.join(v['expected_docs'])}")
            print()

    if soft_warnings:
        print("=" * 60)
        print("DOC-CODE COUPLING WARNINGS (consider updating)")
        print("=" * 60)
        print()
        for v in soft_warnings:
            print(f"  {v['description']}")
            print(f"    Changed: {', '.join(v['changed_sources'][:3])}")
            if len(v['changed_sources']) > 3:
                print(f"             ... and {len(v['changed_sources']) - 3} more")
            print(f"    Consider: {', '.join(v['expected_docs'])}")
            print()

    print("=" * 60)
    print("If docs are already accurate, update 'Last verified' date.")
    print("=" * 60)

    return 1 if (args.strict and strict_violations) else 0


if __name__ == "__main__":
    sys.exit(main())
