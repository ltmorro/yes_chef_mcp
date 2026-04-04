"""Tests for recipe store CRUD operations."""

from __future__ import annotations

from yes_chef_mcp.core.models import Recipe, RecipeCategory
from yes_chef_mcp.core.recipe_store import (
    delete_recipe,
    get_nutrition,
    get_recipe,
    list_all_categories,
    list_all_tags,
    list_recipes,
)


async def test_get_recipe(sample_recipes: list[Recipe]) -> None:
    recipe = await get_recipe("recipe-chicken")
    assert recipe is not None
    assert recipe.name == "Grilled Chicken Breast"
    assert recipe.category == RecipeCategory.MAIN
    assert len(recipe.ingredients) == 3


async def test_get_recipe_not_found() -> None:
    assert await get_recipe("nonexistent") is None


async def test_list_recipes(sample_recipes: list[Recipe]) -> None:
    recipes = await list_recipes()
    assert len(recipes) == 3


async def test_list_recipes_by_category(sample_recipes: list[Recipe]) -> None:
    mains = await list_recipes(category=RecipeCategory.MAIN)
    assert len(mains) == 2
    assert all(r.category == RecipeCategory.MAIN for r in mains)


async def test_list_recipes_by_tags(sample_recipes: list[Recipe]) -> None:
    quick = await list_recipes(tags=["quick"])
    assert len(quick) == 1
    assert quick[0].id == "recipe-chicken"


async def test_get_nutrition(sample_recipes: list[Recipe]) -> None:
    nutr = await get_nutrition("recipe-chicken")
    assert nutr is not None
    assert nutr.calories == 280.0
    assert nutr.protein_g == 45.0


async def test_delete_recipe(sample_recipes: list[Recipe]) -> None:
    assert await delete_recipe("recipe-chicken")
    assert await get_recipe("recipe-chicken") is None
    assert await get_nutrition("recipe-chicken") is None


async def test_list_all_tags(sample_recipes: list[Recipe]) -> None:
    tags = await list_all_tags()
    assert "dinner" in tags
    assert "quick" in tags
    assert "vegetarian" in tags


async def test_list_all_categories(sample_recipes: list[Recipe]) -> None:
    cats = await list_all_categories()
    assert "main" in cats
    assert "side" in cats
