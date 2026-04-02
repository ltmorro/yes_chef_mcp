"""Tests for grocery list generation."""

from __future__ import annotations

from datetime import date

from mealmcp.core.grocery import generate_grocery_list
from mealmcp.core.models import MealType, Recipe
from mealmcp.core.planner import add_meal_slot, create_meal_plan


def test_generate_grocery_list(
    sample_family_id: str, sample_recipes: list[Recipe]
) -> None:
    plan = create_meal_plan(sample_family_id, "Test Week", date(2026, 4, 1))
    add_meal_slot(plan.id, 0, MealType.DINNER, "recipe-chicken")
    add_meal_slot(plan.id, 0, MealType.DINNER, "recipe-quinoa")

    grocery = generate_grocery_list(plan.id)
    assert len(grocery.items) > 0

    item_names = {item.name.lower() for item in grocery.items}
    assert "chicken breast" in item_names
    assert "quinoa" in item_names


def test_grocery_excludes_pantry(
    sample_family_id: str, sample_recipes: list[Recipe]
) -> None:
    plan = create_meal_plan(sample_family_id, "Test", date(2026, 4, 1))
    add_meal_slot(plan.id, 0, MealType.DINNER, "recipe-chicken")

    grocery = generate_grocery_list(plan.id, exclude_pantry=True)
    item_names = {item.name.lower() for item in grocery.items}
    assert "olive oil" not in item_names


def test_grocery_includes_pantry_when_disabled(
    sample_family_id: str, sample_recipes: list[Recipe]
) -> None:
    plan = create_meal_plan(sample_family_id, "Test", date(2026, 4, 1))
    add_meal_slot(plan.id, 0, MealType.DINNER, "recipe-chicken")

    grocery = generate_grocery_list(plan.id, exclude_pantry=False)
    item_names = {item.name.lower() for item in grocery.items}
    assert "olive oil" in item_names


def test_grocery_category_guessing(
    sample_family_id: str, sample_recipes: list[Recipe]
) -> None:
    plan = create_meal_plan(sample_family_id, "Test", date(2026, 4, 1))
    add_meal_slot(plan.id, 0, MealType.DINNER, "recipe-chicken")

    grocery = generate_grocery_list(plan.id)
    chicken_items = [i for i in grocery.items if "chicken" in i.name.lower()]
    assert chicken_items
    assert chicken_items[0].category == "protein"
