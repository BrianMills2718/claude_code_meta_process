# Claude Code Meta-Process

A collection of patterns for coordinating AI coding assistants (Claude Code, Cursor, etc.) on shared codebases.

## What This Solves

- **Parallel work conflicts** - Multiple instances editing the same files
- **Context loss** - AI forgetting project conventions mid-session
- **Documentation drift** - Docs diverging from code over time
- **AI drift** - AI guessing instead of investigating

## Quick Start

```bash
# Clone this repo
git clone https://github.com/BrianMills2718/claude_code_meta_process.git

# Copy to your project
cp -r claude_code_meta_process/* your-project/meta-process/
cp claude_code_meta_process/meta-process.yaml.example your-project/meta-process.yaml

# Or use the install script
./install.sh /path/to/your-project
```

## Documentation

- [Getting Started](GETTING_STARTED.md) - Step-by-step adoption guide
- [Patterns](patterns/01_README.md) - All 29 patterns
- [Hooks](hooks/README.md) - Git and Claude Code hooks

## Patterns Overview

| Category | Patterns |
|----------|----------|
| **Core Workflow** | Worktrees, Claims, Plans |
| **Quality** | Testing, Mocking, Doc-Code Coupling |
| **Planning** | Question-Driven, Uncertainty Tracking, Conceptual Modeling |
| **Coordination** | PR Review, Ownership Respect |

## Configuration

Edit `meta-process.yaml` to control enforcement:

```yaml
weight: medium  # minimal | light | medium | heavy

planning:
  question_driven_planning: advisory  # disabled | advisory | required
  uncertainty_tracking: advisory
  warn_on_unverified_claims: true

project:
  type: existing  # new | existing | prototype
  complexity: moderate  # simple | moderate | complex
```

## Origin

Developed and stress-tested in [agent_ecology](https://github.com/BrianMills2718/agent_ecology2).

## Version

1.0.0

Generated: 2026-01-28
