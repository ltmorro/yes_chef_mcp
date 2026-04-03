# CLAUDE.md

## Project Overview

**MealMCP** (Yes Chef) — a self-hosted meal planning MCP server with macro-nutrient optimization.
FastAPI REST API + FastMCP server in a single ASGI process backed by async SQLite (WAL mode).

## Quick Reference

```bash
# All commands run from /server
cd server

# Install dependencies
uv sync --all-extras

# Run the server
uv run uvicorn mealmcp.app:app --reload

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=mealmcp

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check (mypy currently, migrating to ty when stable)
uv run mypy mealmcp/
```

## Architecture

```
server/mealmcp/
├── app.py              # FastAPI + FastMCP unified ASGI entry
├── api/routes.py       # REST endpoints (/api/*)
├── mcp/server.py       # MCP tool definitions (/mcp/sse)
├── core/               # Domain logic
│   ├── models.py       # Dataclass domain models + enums
│   ├── schemas.py      # Pydantic models (API boundaries only)
│   ├── db.py           # Async SQLite connection + schema init
│   ├── recipe_store.py # Recipe CRUD + embeddings
│   ├── search.py       # Hybrid FTS5 + vector search (RRF fusion)
│   ├── meal_composer.py# Meal composition + complement suggestions
│   ├── planner.py      # Meal plan CRUD
│   ├── optimizer.py    # MILP solver + heuristic fallback
│   ├── constraint_relaxer.py # Progressive constraint relaxation
│   └── grocery.py      # Grocery list generation
└── pipeline/           # Data enrichment
    ├── embeddings.py   # Sentence-transformer embeddings (384-dim)
    ├── nutrition.py    # USDA / Nutritionix enrichment
    └── providers/      # Recipe import plugins (CSV, AnyList, Mealie)
```

## Code Conventions

### Python & Tooling
- **Python 3.12+** required
- **uv** for package management — no pip, no poetry
- **ruff** for linting and formatting (line length: 99)
- **mypy** strict mode for type checking (migrating to **ty** when stable)
- **pytest** + **pytest-asyncio** (auto mode) for tests

### Type Hints
- Type annotations are **required** on all functions and variables where not trivially inferred
- `Any` is **never acceptable** — find the real type or use a protocol/union/generic
- Use `typing` imports only when needed (prefer built-in generics: `list[str]`, `dict[str, int]`)

### Data Modeling
- **Pydantic models** at system edges only: API request/response schemas (`core/schemas.py`)
- **Dataclasses** for all internal domain models (`core/models.py`)
- Prefer frozen dataclasses for immutable value objects
- Use `__slots__` where appropriate for performance

### Style
- Practical > clever. Write code a tired engineer can read at 2am
- Don't over-abstract — three similar lines beats a premature abstraction
- Small user scale initially — don't overengineer
- Async-first for I/O (aiosqlite, httpx)

### Database
- SQLite in WAL mode — per-request connections, no connection pool needed
- sqlite-vec extension for vector similarity
- FTS5 for keyword search
- Schema versioned via `schema_version` table

## Collaboration Rules

- **Push back** if you disagree — suggest alternatives with reasoning
- **Before big changes** that touch multiple files or shift patterns: propose a plan first and get approval
- Keep PRs focused — one concern per change
- Tests required for new functionality

## Testing

Tests live in `server/tests/`. Each test gets a fresh temp database via fixtures in `conftest.py`.

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_search.py

# Run with verbose output
uv run pytest -v

# Run with coverage
uv run pytest --cov=mealmcp --cov-report=term-missing
```

## Key Design Decisions

1. **Tiered optimization**: MILP (python-mip/CBC) → greedy + simulated annealing → scipy continuous relaxation. Never returns "infeasible" — constraint relaxer cascades until a solution is found.
2. **Hybrid search**: FTS5 keyword + sentence-transformer vectors fused via Reciprocal Rank Fusion (2x keyword boost).
3. **Unified ASGI**: FastAPI REST + FastMCP SSE share one process and one SQLite database.
4. **Provider pattern**: Recipe importers implement a base interface (`pipeline/providers/base.py`) for extensibility.

## External API Keys

Nutrition enrichment keys are passed as constructor args to `NutritionEnricher`:
- `usda_api_key` — USDA FoodData Central (optional)
- `nutritionix_app_id` + `nutritionix_app_key` — Nutritionix (optional)

Database path is hardcoded to `/data/mealmcp.db` in `core/db.py` (configurable via `configure_database()`).
