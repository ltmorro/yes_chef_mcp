"""Regenerate the fake-host test fixtures in frontend/tests/host/fixtures/.

Seeds a throwaway SQLite database with two recipes, one member and one plan,
calls the real show_* tools (and set_macro_target) through an in-memory
FastMCP client, and writes each tool result as JSON. The embeddings module is
blocked so search runs FTS-only: no model download, no network.

    cd backend && uv run python scripts/record_view_fixtures.py
"""

import asyncio
import json
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

# Block sentence-transformers before anything imports it (search falls back to FTS).
sys.modules["yes_chef_mcp.pipeline.embeddings"] = None  # type: ignore[assignment]

from fastmcp import Client  # noqa: E402
from fastmcp.client.client import CallToolResult  # noqa: E402
from mcp.types import TextContent  # noqa: E402

from yes_chef_mcp.core.db import configure_db_path, get_db  # noqa: E402
from yes_chef_mcp.core.models import (  # noqa: E402
    Ingredient,
    MealType,
    Nutrition,
    NutritionSource,
    Recipe,
    RecipeCategory,
    RecipeSource,
)
from yes_chef_mcp.core.planner import add_meal_slot  # noqa: E402
from yes_chef_mcp.core.recipe_store import (  # noqa: E402
    index_recipe_fts,
    upsert_nutrition,
    upsert_recipe,
)
from yes_chef_mcp.mcp.server import mcp  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "frontend" / "tests" / "host" / "fixtures"
PLAN_ID = "plan-spring"
MEMBER_ID = "m1"
JsonObject = dict[str, object]
IngredientRow = tuple[str, float, str | None]
INSTRUCTIONS = {
    "r1": "1. Pat the chicken dry and season it.\n"
    "2. Sear for 5 minutes per side.\n"
    "3. Squeeze the lemon over and rest 2 minutes.",
}


def dump(result: CallToolResult) -> JsonObject:
    """The tool result as the host forwards it to a view (MCP CallToolResult shape)."""
    text = [{"type": "text", "text": c.text} for c in result.content if isinstance(c, TextContent)]
    return {"content": text, "structuredContent": result.structured_content, "isError": False}


async def seed() -> None:
    now = datetime(2026, 4, 1, 12, 0)
    async with get_db() as db:
        await db.execute("INSERT INTO families (id, name, provider) VALUES ('f1', 'F', 'csv')")
        await db.execute(
            "INSERT INTO members (id, family_id, name, role, is_default) "
            "VALUES (?, 'f1', 'Alex', 'admin', 1)",
            (MEMBER_ID,),
        )
        await db.execute(
            "INSERT INTO meal_plans (id, family_id, name, start_date, days, created_at) "
            "VALUES (?, 'f1', 'Spring Week', ?, 7, ?)",
            (PLAN_ID, date(2026, 4, 1).isoformat(), now.isoformat()),
        )
    recipes: list[tuple[str, str, list[IngredientRow], int]] = [
        ("r1", "Lemon Chicken", [("chicken breast", 2.0, "lb"), ("lemon", 1.0, None)], 450),
        ("r2", "Garlic Rice", [("rice", 1.0, "cup"), ("garlic", 3.0, "cloves")], 320),
    ]
    for rid, name, ingredients, calories in recipes:
        recipe = Recipe(
            id=rid,
            family_id="f1",
            name=name,
            source=RecipeSource.MANUAL,
            category=RecipeCategory.MAIN,
            tags=["dinner"],
            ingredients=[Ingredient(name=n, quantity=q, unit=u) for n, q, u in ingredients],
            instructions=INSTRUCTIONS.get(rid, ""),
            created_at=now,
            updated_at=now,
        )
        await upsert_recipe(recipe)
        await index_recipe_fts(recipe)
        await upsert_nutrition(
            Nutrition(
                recipe_id=rid,
                calories=calories,
                protein_g=40,
                carbs_g=30,
                fat_g=10,
                source=NutritionSource.USDA,
                computed_at=now,
            )
        )
    await add_meal_slot(PLAN_ID, 0, MealType.DINNER, "r1")
    await add_meal_slot(PLAN_ID, 1, MealType.DINNER, "r2")


async def main() -> None:
    configure_db_path(Path(tempfile.mkdtemp()) / "fixtures.db")
    await seed()
    OUT.mkdir(parents=True, exist_ok=True)
    results: dict[str, JsonObject] = {}

    async with Client(mcp) as client:
        macro = {"member_id": MEMBER_ID, "name": "Cut", "protein_g": 150, "carbs_g": 200}
        await client.call_tool("set_macro_target", {**macro, "calories": 1940, "fat_g": 60})

        # Cook mode for the day-0 dinner, scaled to 3 servings of a 1-serving recipe
        slot: JsonObject = {"plan_id": PLAN_ID, "day_offset": 0, "meal_type": "dinner"}
        calls: dict[str, tuple[str, JsonObject]] = {
            "macro-setter": ("show_macro_target_setter", {}),
            "recipe-selector": ("show_recipe_selector", {}),
            "weekly-calendar": (
                "show_weekly_calendar",
                {"plan_id": PLAN_ID, "member_id": MEMBER_ID},
            ),
            "weekly-calendar-nomember": ("show_weekly_calendar", {"plan_id": PLAN_ID}),
            "grocery-list": ("show_grocery_checklist", {"plan_id": PLAN_ID}),
            "cook-mode": (
                "show_cook_mode",
                {"recipe_id": "r1", "servings": 3, **slot},
            ),
        }
        for key, (tool, args) in calls.items():
            results[key] = dump(await client.call_tool(tool, args))

        # What the fake host answers to view-initiated tools/call: a refresh after
        # a lunch was added (so the re-render is visible), and a macro save.
        await add_meal_slot(PLAN_ID, 2, MealType.LUNCH, "r2")
        refreshed = await client.call_tool(
            "show_weekly_calendar", {"plan_id": PLAN_ID, "member_id": MEMBER_ID}
        )
        results["weekly-calendar-refreshed"] = dump(refreshed)
        saved = await client.call_tool(
            "set_macro_target", {**macro, "calories": 2165, "fat_g": 65, "set_active": True}
        )
        results["set-macro-target"] = dump(saved)
        logged = await client.call_tool(
            "log_cooked_meal",
            {"recipe_id": "r1", "servings": 3, "rating": "good", **slot},
        )
        results["log-cooked-meal"] = dump(logged)

    for key, result in results.items():
        OUT.joinpath(f"{key}.json").write_text(json.dumps(result, indent=2) + "\n")
        print(f"wrote {OUT / key}.json")


if __name__ == "__main__":
    asyncio.run(main())
