# pipeline/CLAUDE.md

Data enrichment and import pipelines. These feed into `core/` but never depend on API or MCP layers.

## Embeddings

- `embeddings.py` — generates 384-dim vectors via sentence-transformers
- Vectors stored in sqlite-vec and used by `core/search.py` for semantic similarity

## Nutrition Enrichment

- `nutrition.py` — `NutritionEnricher` looks up ingredients against USDA FoodData Central, falls back to Nutritionix
- API keys are constructor args (both optional — graceful degradation to manual entry)
- Per-ingredient lookup with confidence scoring, then aggregated to per-serving nutrition

## Recipe Providers

- `providers/base.py` — base interface all importers implement
- `providers/csv_import.py` — CSV file import
- `providers/anylist.py` — AnyList sync
- `providers/mealie.py` — Mealie import

To add a new provider: implement the base interface and register in `providers/__init__.py`.
