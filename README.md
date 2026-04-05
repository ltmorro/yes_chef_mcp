# Yes Chef MCP

Self-hosted meal planning optimization server with macro-nutrient targeting. Exposes both a REST API (for web UIs) and an MCP server (for Claude Desktop) from a single process. It enables AI assistants (like Claude) to seamlessly integrate with your personal recipe database to search recipes, compose nutritionally balanced meals, optimize full-week plans based on member-specific macro targets, and generate consolidated grocery lists.

## Key Features

- **Hybrid Recipe Search:** Combines Full-Text Search (FTS5) for keyword matching with semantic vector similarity (`sqlite-vec`) using Reciprocal Rank Fusion (RRF).
- **Macro Optimization:** Uses a tiered solving strategy (Mixed Integer Linear Programming via `python-mip`, followed by greedy heuristics and continuous relaxation) to find the best recipe combinations to meet per-member macro goals. Always returns a result.
- **Interactive UI (MCP Apps):** Provides embedded React-based UI components (like a macro target setter, recipe selector, and grocery checklist) that render directly within compatible MCP clients.
- **Family Planning:** Supports individual macro targets for different family members, calculating per-member serving sizes for shared meals.
- **Smart Grocery Lists:** Consolidates ingredients across meal plans, automatically merging similar items and excluding common pantry staples.
- **Nutrition Enrichment:** Auto-populate macro data from USDA FoodData Central or Nutritionix.
- **Multi-source Import:** Pull recipes from AnyList, Mealie, CSV, or enter manually.

## Prerequisites

- **Python:** 3.12 or higher.
- **Package Manager:** [uv](https://docs.astral.sh/uv/) is recommended for Python dependency management.
- **Node.js & npm:** Required for building the React-based interactive UI components.
- **Database:** SQLite is used as the primary data store, leveraging the `sqlite-vec` extension for vector embeddings.

## Quickstart

### 1. Install Python Dependencies
Navigate to the server directory and sync dependencies using `uv`:
```bash
cd backend
uv sync --all-extras
```

### 2. Build Frontend Views
The interactive MCP App components must be built before running the server:
```bash
cd frontend
npm install
npm run build
```

### 3. Run the Application
Start the unified FastAPI + FastMCP server:
```bash
cd backend
uv run python -m yes_chef_mcp.app
# OR
uv run uvicorn yes_chef_mcp.app:app --reload
```

By default, the server runs on `http://127.0.0.1:8000`. 
* **REST API:** `http://127.0.0.1:8000/api/*`
* **Static Views:** `http://127.0.0.1:8000/views/static/*`
* **MCP HTTP Endpoint:** `http://127.0.0.1:8000/mcp`

## Claude Desktop Integration

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "yes-chef": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

## Configuration

- **Database path**: defaults to `data/yes_chef_mcp.db`, configurable via `YES_CHEF_DB_PATH` env var or `configure_db_path()` in `core/db.py`
- **Nutrition APIs** (optional): USDA FoodData Central and Nutritionix keys are passed to `NutritionEnricher` at construction time

## Development

```bash
cd backend

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

```text
backend/yes_chef_mcp/
├── app.py                # Unified FastAPI + FastMCP entry point
├── api/                  # REST API routes and HTML view controllers
│   └── routes.py         # REST API endpoints
├── mcp/                  # MCP server definition and tool wrappers (`server.py`)
│   └── server.py         # MCP tool definitions
├── core/                 # Core domain logic
│   ├── models.py         # Domain models (dataclasses)
│   ├── schemas.py        # API schemas (Pydantic)
│   ├── db.py             # Async SQLite connection pooling (WAL mode)
│   ├── recipe_store.py   # Recipe CRUD, FTS, and vector embeddings
│   ├── search.py         # Hybrid and macro-distance search algorithms
│   ├── meal_composer.py  # Ad-hoc meal composition and macro calculations
│   ├── planner.py        # Meal plan CRUD and scheduling
│   ├── optimizer.py      # MILP and greedy optimization engines
│   ├── constraint_relaxer.py  # Logic for relaxing optimization constraints
│   └── grocery.py        # Smart grocery list generation
├── pipeline/             # Data ingestion (Nutrition APIs, Mealie/AnyList imports)
│   ├── embeddings.py     # Sentence-transformer embeddings
│   ├── nutrition.py      # External nutrition APIs
│   └── providers/        # Recipe import plugins
└── tests/                # Comprehensive test suite for all core logic

frontend/                 # React/Vite source for interactive UI components
├── src/
│   ├── components/       # Shared React components
│   ├── entries/          # Per-page entry points
│   ├── bridge.ts         # API communication
│   ├── theme.ts          # Design token exports
│   └── types.ts          # Shared TypeScript types
└── dist/                 # Vite build output (served by FastAPI)
```

### Key Design Choices

- **Pydantic at edges, dataclasses internally** — validation where data enters the system, lightweight models everywhere else
- **Tiered optimization** — MILP solver with progressive constraint relaxation, falling back to heuristics. Always returns a result.
- **Hybrid search** — FTS5 keyword search + 384-dim vector similarity fused via Reciprocal Rank Fusion
- **Single process** — FastAPI and FastMCP share one ASGI app, one SQLite database in WAL mode
- **Async-first** — aiosqlite for non-blocking database access, httpx for external API calls

## License

MIT
