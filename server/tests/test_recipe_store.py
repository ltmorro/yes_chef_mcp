"""Tests for recipe store CRUD operations."""

from __future__ import annotations

from mealmcp.core.models import Recipe, RecipeCategory
from mealmcp.core.recipe_store import (
    delete_recipe,
    get_nutrition,
    get_recipe,
    list_all_categories,
    list_all_tags,
    list_recipes,
)


def test_get_recipe(sample_recipes: list[Recipe]) -> None:
    recipe = get_recipe("recipe-chicken")
    assert recipe is not None
    assert recipe.name == "Grilled Chicken Breast"
    assert recipe.category == RecipeCategory.MAIN
    assert len(recipe.ingredients) == 3


def test_get_recipe_not_found() -> None:
    assert get_recipe("nonexistent") is None


def test_list_recipes(sample_recipes: list[Recipe]) -> None:
    recipes = list_recipes()
    assert len(recipes) == 3


def test_list_recipes_by_category(sample_recipes: list[Recipe]) -> None:
    mains = list_recipes(category=RecipeCategory.MAIN)
    assert len(mains) == 2
    assert all(r.category == RecipeCategory.MAIN for r in mains)


def test_list_recipes_by_tags(sample_recipes: list[Recipe]) -> None:
    quick = list_recipes(tags=["quick"])
    assert len(quick) == 1
    assert quick[0].id == "recipe-chicken"


def test_get_nutrition(sample_recipes: list[Recipe]) -> None:
    nutr = get_nutrition("recipe-chicken")
    assert nutr is not None
    assert nutr.calories == 280.0
    assert nutr.protein_g == 45.0


def test_delete_recipe(sample_recipes: list[Recipe]) -> None:
    assert delete_recipe("recipe-chicken")
    assert get_recipe("recipe-chicken") is None
    assert get_nutrition("recipe-chicken") is None


def test_list_all_tags(sample_recipes: list[Recipe]) -> None:
    tags = list_all_tags()
    assert "dinner" in tags
    assert "quick" in tags
    assert "vegetarian" in tags


def test_list_all_categories(sample_recipes: list[Recipe]) -> None:
    cats = list_all_categories()
    assert "main" in cats
    assert "side" in cats
