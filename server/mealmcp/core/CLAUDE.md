# core/CLAUDE.md

Domain logic layer. No HTTP or MCP concerns leak in here.

## Data Modeling

- `models.py` — all domain types as dataclasses + enums. Frozen where possible.
- `schemas.py` — Pydantic models for API boundaries only. These mirror the dataclasses but add validation.

## Database

- `db.py` — async SQLite via aiosqlite in WAL mode. Per-request connections (lightweight under WAL).
- sqlite-vec extension loaded for vector similarity search
- FTS5 virtual table for keyword search
- Schema versioned via `schema_version` table — bump on migrations

## Search

- `search.py` — hybrid FTS5 keyword + 384-dim vector similarity
- Results fused via Reciprocal Rank Fusion (2x keyword boost)
- `macro_distance_search()` finds recipes by weighted Euclidean distance to macro targets

## Optimization

- `optimizer.py` — tiered: MILP (python-mip/CBC) → greedy + simulated annealing → scipy continuous relaxation
- `constraint_relaxer.py` — progressive cascade that widens tolerances until a solution is found. Never returns infeasible.
- Relaxation order: allow repeats → widen macros → drop prep time → drop tags → widen servings → drop categories → heuristic

## Key Modules

- `recipe_store.py` — recipe CRUD, nutrition storage, FTS/embedding indexing
- `meal_composer.py` — assemble meals from recipes, compute per-member deviations, suggest complements
- `planner.py` — meal plan CRUD (create, slot assignment, listing)
- `grocery.py` — aggregate ingredients into categorized shopping lists
