"""Tests for cook mode: step splitting, timer parsing, scaling, and the meal log."""

from __future__ import annotations

import pytest

from yes_chef_mcp.core.cook_mode import (
    cook_steps,
    log_cooked_meal,
    parse_timer_seconds,
    scale_ingredients,
    split_steps,
)
from yes_chef_mcp.core.db import get_db
from yes_chef_mcp.core.models import CookRating, Ingredient, MealType, Recipe

# ── split_steps ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("instructions", "expected"),
    [
        ("", []),
        ("   \n\n  ", []),
        ("Grill chicken at 400F for 20 minutes.", ["Grill chicken at 400F for 20 minutes."]),
        ("Chop onions\nFry them", ["Chop onions", "Fry them"]),
        ("1. Chop onions\n2. Fry them", ["Chop onions", "Fry them"]),
        ("1) Chop onions\r\n\r\n2) Fry them\r\n", ["Chop onions", "Fry them"]),
        ("Step 1: Chop onions\nStep 2 - Fry them", ["Chop onions", "Fry them"]),
        ("- Chop onions\n* Fry them\n• Serve", ["Chop onions", "Fry them", "Serve"]),
        # A bare "Step 1" heading on its own line is dropped, not kept as a step
        ("Step 1\nChop onions\nStep 2\nFry them", ["Chop onions", "Fry them"]),
        # One paragraph is split into sentences
        (
            "Cook pasta. Drain it! Toss with sauce.",
            ["Cook pasta.", "Drain it!", "Toss with sauce."],
        ),
        ("1. Cook pasta. 2. Drain it.", ["Cook pasta.", "Drain it."]),
        # A quantity at the start of a line is not a step number
        ("1.5 cups of stock go in\n2 eggs, beaten", ["1.5 cups of stock go in", "2 eggs, beaten"]),
    ],
)
def test_split_steps(instructions: str, expected: list[str]) -> None:
    assert split_steps(instructions) == expected


def test_split_steps_keeps_multi_sentence_lines_whole() -> None:
    text = "Preheat the oven. Grease a pan.\nBake. Let cool."
    assert split_steps(text) == ["Preheat the oven. Grease a pan.", "Bake. Let cool."]


# ── parse_timer_seconds ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Chop the onions.", None),
        ("Bake at 350F.", None),
        ("Simmer for 20 minutes.", 1200),
        ("Simmer for 20 min", 1200),
        ("Simmer 5 mins, stirring", 300),
        ("Roast for 1 hour", 3600),
        ("Roast 2 hrs", 7200),
        ("Rest 30 seconds", 30),
        ("Boil 10-12 minutes", 720),
        ("Boil 10 \u2013 12 minutes", 720),
        ("Boil 5 to 7 minutes", 420),
        ("Braise for 1.5 hours", 5400),
        ("Braise for 1½ hours", 5400),
        ("Roast 1 hour 15 minutes", 4500),
        ("Roast 1 hour and 15 minutes", 4500),
        # Only the first duration: separate actions are not added together
        ("Sear 3 minutes, then bake 20 minutes", 180),
        ("Bake 1 hour, then rest 10 minutes", 3600),
        ("Bake 0 minutes", None),
    ],
)
def test_parse_timer_seconds(text: str, expected: int | None) -> None:
    assert parse_timer_seconds(text) == expected


def test_cook_steps_numbers_from_one_with_timers() -> None:
    steps = cook_steps("1. Chop onions\n2. Fry for 5 minutes")
    assert [(s.index, s.text, s.timer_seconds) for s in steps] == [
        (1, "Chop onions", None),
        (2, "Fry for 5 minutes", 300),
    ]


# ── scale_ingredients ─────────────────────────────────────────────────────


def test_scale_ingredients() -> None:
    ingredients = [
        Ingredient(name="rice", quantity=1.0, unit="cup"),
        Ingredient(name="garlic", quantity=3.0, unit="cloves"),
        Ingredient(name="salt"),
    ]
    scaled = scale_ingredients(ingredients, 1 / 3)
    assert [(i.name, i.quantity, i.unit) for i in scaled] == [
        ("rice", 0.33, "cup"),
        ("garlic", 1.0, "cloves"),
        ("salt", None, None),
    ]


# ── log_cooked_meal ───────────────────────────────────────────────────────


async def test_log_cooked_meal_inserts_a_row(sample_recipes: list[Recipe]) -> None:
    entry = await log_cooked_meal("recipe-chicken", 2.0, CookRating.GOOD, None, None, None)
    again = await log_cooked_meal("recipe-chicken", 1.0)
    assert entry.id != again.id

    async with get_db() as db, db.execute("SELECT * FROM meal_log ORDER BY servings") as cursor:
        rows = await cursor.fetchall()

    assert [(r["servings"], r["rating"], r["meal_type"]) for r in rows] == [
        (1.0, None, None),
        (2.0, "good", None),
    ]


async def test_log_cooked_meal_with_slot(sample_recipes: list[Recipe]) -> None:
    entry = await log_cooked_meal("recipe-chicken", 1.0, CookRating.BAD, None, 3, MealType.DINNER)
    assert entry.day_offset == 3
    assert entry.meal_type == MealType.DINNER

    async with get_db() as db, db.execute("SELECT * FROM meal_log") as cursor:
        row = await cursor.fetchone()
    assert row is not None
    assert (row["day_offset"], row["meal_type"], row["rating"]) == (3, "dinner", "bad")
