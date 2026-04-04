"""Tests for meal plan CRUD."""

from __future__ import annotations

from datetime import date

from yes_chef_mcp.core.models import MealType, Recipe
from yes_chef_mcp.core.planner import (
    add_meal_slot,
    create_meal_plan,
    delete_meal_plan,
    get_meal_plan,
    get_meal_slots,
    list_meal_plans,
    remove_meal_slot,
)


async def test_create_and_get_plan(sample_family_id: str) -> None:
    plan = await create_meal_plan(
        family_id=sample_family_id,
        name="Test Week",
        start_date=date(2026, 4, 1),
        days=7,
    )
    assert plan.name == "Test Week"
    assert plan.days == 7

    fetched = await get_meal_plan(plan.id)
    assert fetched is not None
    assert fetched.name == plan.name


async def test_list_plans(sample_family_id: str) -> None:
    await create_meal_plan(sample_family_id, "Week 1", date(2026, 4, 1))
    await create_meal_plan(sample_family_id, "Week 2", date(2026, 4, 8))

    plans = await list_meal_plans(sample_family_id)
    assert len(plans) == 2


async def test_add_and_get_slots(
    sample_family_id: str, sample_recipes: list[Recipe]
) -> None:
    plan = await create_meal_plan(sample_family_id, "Test", date(2026, 4, 1))

    await add_meal_slot(plan.id, 0, MealType.DINNER, "recipe-chicken", 1.0)
    await add_meal_slot(plan.id, 0, MealType.DINNER, "recipe-quinoa", 1.0)

    slots = await get_meal_slots(plan.id, day_offset=0)
    assert len(slots) == 2


async def test_remove_slot(
    sample_family_id: str, sample_recipes: list[Recipe]
) -> None:
    plan = await create_meal_plan(sample_family_id, "Test", date(2026, 4, 1))
    await add_meal_slot(plan.id, 0, MealType.DINNER, "recipe-chicken")

    assert await remove_meal_slot(plan.id, 0, MealType.DINNER, "recipe-chicken")
    slots = await get_meal_slots(plan.id, day_offset=0)
    assert len(slots) == 0


async def test_delete_plan(sample_family_id: str) -> None:
    plan = await create_meal_plan(sample_family_id, "Test", date(2026, 4, 1))
    assert await delete_meal_plan(plan.id)
    assert await get_meal_plan(plan.id) is None


async def test_member_servings(
    sample_family_id: str, sample_recipes: list[Recipe]
) -> None:
    plan = await create_meal_plan(sample_family_id, "Test", date(2026, 4, 1))
    slot = await add_meal_slot(
        plan.id, 0, MealType.DINNER, "recipe-chicken",
        servings=1.0,
        member_servings={"alex": 1.0, "jordan": 1.5},
    )
    assert slot.member_servings == {"alex": 1.0, "jordan": 1.5}
