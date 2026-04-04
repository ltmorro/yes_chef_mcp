# Yes Chef MCP

Self-hosted meal planning optimization server with macro-nutrient targeting. Exposes both a REST API (for web UIs) and an MCP server (for Claude Desktop) from a single process.

## What It Does

- **Meal plan optimization** — generates weekly/monthly plans that hit per-member macro targets using Mixed Integer Linear Programming, with automatic fallback to heuristics when constraints are tight
- **Recipe management** — store, tag, categorize, and search recipes with hybrid keyword + semantic search
- **Nutrition enrichment** — auto-populate macro data from USDA FoodData Central or Nutritionix
- **Grocery list generation** — aggregate ingredients across meal plans into categorized shopping lists
- **Multi-source import** — pull recipes from AnyList, Mealie, CSV, or enter manually

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

## Quick Start

```bash
cd server

# Install dependencies
uv sync --all-extras

# Run the server
uv run uvicorn yes_chef_mcp.app:app --reload
```

The server starts with:
- REST API at `http://localhost:8000/api/`
- MCP SSE endpoint at `http://localhost:8000/mcp/sse`

### Claude Desktop Integration

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "yes-chef": {
      "url": "http://localhost:8000/mcp/sse"
    }
  }
}
```

## Configuration

- **Database path**: defaults to `/data/yes_chef_mcp.db`, configurable via `configure_database()` in `core/db.py`
- **Nutrition APIs** (optional): USDA FoodData Central and Nutritionix keys are passed to `NutritionEnricher` at construction time

## Development

```bash
cd server

# Install with dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Lint & format
uv run ruff check .
uv run ruff format .

# Type check
uv run mypy yes_chef_mcp/
```

## Architecture

```
server/yes_chef_mcp/
├── app.py                # Unified FastAPI + FastMCP entry point
├── api/routes.py         # REST API endpoints
├── mcp/server.py         # MCP tool definitions
├── core/
│   ├── models.py         # Domain models (dataclasses)
│   ├── schemas.py        # API schemas (Pydantic)
│   ├── db.py             # Async SQLite (WAL mode)
│   ├── recipe_store.py   # Recipe CRUD + search indexing
│   ├── search.py         # Hybrid FTS5 + vector search
│   ├── meal_composer.py  # Meal composition & suggestions
│   ├── planner.py        # Meal plan operations
│   ├── optimizer.py      # MILP + heuristic optimization
│   ├── constraint_relaxer.py  # Graceful constraint relaxation
│   └── grocery.py        # Shopping list generation
└── pipeline/
    ├── embeddings.py     # Sentence-transformer embeddings
    ├── nutrition.py      # External nutrition APIs
    └── providers/        # Recipe import plugins
```

### Key Design Choices

- **Pydantic at edges, dataclasses internally** — validation where data enters the system, lightweight models everywhere else
- **Tiered optimization** — MILP solver with progressive constraint relaxation, falling back to heuristics. Always returns a result.
- **Hybrid search** — FTS5 keyword search + 384-dim vector similarity fused via Reciprocal Rank Fusion
- **Single process** — FastAPI and FastMCP share one ASGI app, one SQLite database in WAL mode
- **Async-first** — aiosqlite for non-blocking database access, httpx for external API calls

## License

MIT
