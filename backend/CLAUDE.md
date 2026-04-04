# backend/CLAUDE.md

## Quick Reference

```bash
# All commands run from this directory
uv sync --all-extras          # Install deps
uv run uvicorn yes_chef_mcp.app:app --reload  # Run backend
uv run pytest                 # Tests
uv run pytest --cov=yes_chef_mcp --cov-report=term-missing  # Coverage
uv run ruff check .           # Lint
uv run ruff format .          # Format
uv run mypy yes_chef_mcp/          # Type check
```

## Entry Point

`yes_chef_mcp/app.py` — unified FastAPI + FastMCP ASSI app.
- REST API mounted at `/api/` (routes in `yes_chef_mcp/api/routes.py`)
- MCP HTTP endpoint at `/mcp` (tools in `yes_chef_mcp/mcp/server.py`)

Both share one process and one SQLite database.

## Testing

Tests in `tests/`. Each test gets a fresh temp database via fixtures in `conftest.py`.

```bash
uv run pytest tests/test_search.py   # Single file
uv run pytest -v                     # Verbose
uv run pytest -k "test_hybrid"       # By name
```

## Configuration

- Database path defaults to `data/yes_chef_mcp.db`, override via `YES_CHEF_DB_PATH` env var or `core.db.configure_db_path()`
- Nutrition API keys passed as constructor args to `pipeline.nutrition.NutritionEnricher`
- All tool config (ruff, mypy, pytest) lives in `pyproject.toml`
