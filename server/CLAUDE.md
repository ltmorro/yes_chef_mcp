# server/CLAUDE.md

## Quick Reference

```bash
# All commands run from this directory
uv sync --all-extras          # Install deps
uv run uvicorn mealmcp.app:app --reload  # Run server
uv run pytest                 # Tests
uv run pytest --cov=mealmcp --cov-report=term-missing  # Coverage
uv run ruff check .           # Lint
uv run ruff format .          # Format
uv run mypy mealmcp/          # Type check
```

## Entry Point

`mealmcp/app.py` — unified FastAPI + FastMCP ASSI app.
- REST API mounted at `/api/` (routes in `mealmcp/api/routes.py`)
- MCP SSE endpoint at `/mcp/sse` (tools in `mealmcp/mcp/server.py`)

Both share one process and one SQLite database.

## Testing

Tests in `tests/`. Each test gets a fresh temp database via fixtures in `conftest.py`.

```bash
uv run pytest tests/test_search.py   # Single file
uv run pytest -v                     # Verbose
uv run pytest -k "test_hybrid"       # By name
```

## Configuration

- Database path defaults to `/data/mealmcp.db`, override via `core.db.configure_database()`
- Nutrition API keys passed as constructor args to `pipeline.nutrition.NutritionEnricher`
- All tool config (ruff, mypy, pytest) lives in `pyproject.toml`
