# CLAUDE.md

## Project Overview

**MealMCP** (Yes Chef) — self-hosted meal planning MCP server with macro-nutrient optimization.

## Code Conventions

### Tooling
- **Python 3.12+** required
- **uv** for package management — no pip, no poetry
- **ruff** for linting and formatting (line length: 99)
- **mypy** strict mode for type checking (migrating to **ty** when stable)
- **pytest** + **pytest-asyncio** (auto mode) for tests

### Type Hints
- Type annotations are **required** on all functions and variables where not trivially inferred
- `Any` is **never acceptable** — find the real type or use a protocol/union/generic
- Prefer built-in generics (`list[str]`, `dict[str, int]`) over `typing` imports

### Data Modeling
- **Pydantic models** at system edges only (API request/response schemas)
- **Dataclasses** for all internal domain models
- Prefer frozen dataclasses for immutable value objects

### Style
- Practical > clever. Write code a tired engineer can read at 2am
- Don't over-abstract — three similar lines beats a premature abstraction
- Small user scale initially — don't overengineer
- Async-first for I/O

## Collaboration Rules

- **Push back** if you disagree — suggest alternatives with reasoning
- **Before big changes** that touch multiple files or shift patterns: propose a plan first and get approval
- Keep PRs focused — one concern per change
- Tests required for new functionality
