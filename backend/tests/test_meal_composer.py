"""Tests for meal composition and complement suggestion."""

from __future__ import annotations

from yes_chef_mcp.core.db import get_db
from yes_chef_mcp.core.meal_composer import compose_meal
from yes_chef_mcp.core.models import MealComponent, Recipe


async def test_compose_single_recipe(sample_recipes: list[Recipe]) -> None:
    result = await compose_meal([MealComponent(recipe_id="recipe-chicken", servings=1.0)])
    assert len(result.components) == 1
    assert result.totals.calories == 280.0
    assert result.totals.protein_g == 45.0


async def test_compose_multiple_recipes(sample_recipes: list[Recipe]) -> None:
    result = await compose_meal([
        MealComponent(recipe_id="recipe-chicken", servings=1.0),
        MealComponent(recipe_id="recipe-quinoa", servings=1.0),
    ])
    assert len(result.components) == 2
    assert result.totals.calories == 500.0  # 280 + 220
    assert result.totals.protein_g == 53.0  # 45 + 8


async def test_compose_with_scaled_servings(sample_recipes: list[Recipe]) -> None:
    result = await compose_meal([MealComponent(recipe_id="recipe-chicken", servings=2.0)])
    assert result.totals.calories == 560.0  # 280 * 2
    assert result.totals.protein_g == 90.0  # 45 * 2


async def test_compose_with_member_target(
    sample_recipes: list[Recipe], sample_family_id: str
) -> None:
    async with get_db() as db:
        await db.execute(
            "INSERT INTO members (id, family_id, name) VALUES (?, ?, ?)",
            ("member-alex", sample_family_id, "Alex"),
        )
        await db.execute(
            """INSERT INTO macro_targets (id, member_id, name, calories, protein_g,
               carbs_g, fat_g, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("target-1", "member-alex", "cut", 600, 50, 60, 25, 1),
        )

    result = await compose_meal(
        [MealComponent(recipe_id="recipe-chicken", servings=1.0)],
        member_id="member-alex",
    )
    assert "member-alex" in result.member_deltas
    assert result.member_deltas["member-alex"].calories < 0


async def test_compose_missing_recipe(sample_recipes: list[Recipe]) -> None:
    result = await compose_meal([MealComponent(recipe_id="nonexistent", servings=1.0)])
    assert len(result.components) == 0
    assert result.totals.calories == 0.0
