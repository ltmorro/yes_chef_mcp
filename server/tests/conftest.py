"""Shared test fixtures."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from mealmcp.core.db import configure_db_path, get_db
from mealmcp.core.models import (
    Ingredient,
    Nutrition,
    NutritionSource,
    Recipe,
    RecipeCategory,
    RecipeSource,
)
from mealmcp.core.recipe_store import (
    index_recipe_fts,
    upsert_nutrition,
    upsert_recipe,
)


@pytest.fixture(autouse=True)
async def _fresh_db(tmp_path: Path) -> None:
    """Use a fresh temp database for each test."""
    db_path = tmp_path / "test.db"
    configure_db_path(db_path)
    async with get_db():
        pass


@pytest.fixture()
async def sample_family_id() -> str:
    """Create a sample family and return its ID."""
    family_id = "family-test-1"
    async with get_db() as db:
        await db.execute(
            "INSERT INTO families (id, name, provider) VALUES (?, ?, ?)",
            (family_id, "Test Family", "csv"),
        )
    return family_id


@pytest.fixture()
async def sample_recipes(sample_family_id: str) -> list[Recipe]:
    """Create and return sample recipes with nutrition data."""
    recipes = [
        Recipe(
            id="recipe-chicken",
            family_id=sample_family_id,
            name="Grilled Chicken Breast",
            source=RecipeSource.MANUAL,
            ingredients=[
                Ingredient(name="chicken breast", quantity=2.0, unit="lb"),
                Ingredient(name="olive oil", quantity=2.0, unit="tbsp"),
                Ingredient(name="garlic", quantity=3.0, unit="cloves"),
            ],
            instructions="Grill chicken at 400F for 20 minutes.",
            servings=4,
            prep_minutes=10,
            cook_minutes=20,
            tags=["dinner", "high-protein", "quick"],
            category=RecipeCategory.MAIN,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ),
        Recipe(
            id="recipe-quinoa",
            family_id=sample_family_id,
            name="Quinoa Salad",
            source=RecipeSource.MANUAL,
            ingredients=[
                Ingredient(name="quinoa", quantity=1.0, unit="cup"),
                Ingredient(name="cucumber", quantity=1.0, unit="medium"),
                Ingredient(name="tomato", quantity=2.0, unit="medium"),
                Ingredient(name="lemon juice", quantity=2.0, unit="tbsp"),
            ],
            instructions="Cook quinoa, chop vegetables, mix with lemon juice.",
            servings=2,
            prep_minutes=15,
            cook_minutes=15,
            tags=["side", "vegetarian", "healthy"],
            category=RecipeCategory.SIDE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ),
        Recipe(
            id="recipe-pasta",
            family_id=sample_family_id,
            name="Lemon Garlic Shrimp Pasta",
            source=RecipeSource.MANUAL,
            ingredients=[
                Ingredient(name="pasta", quantity=1.0, unit="lb"),
                Ingredient(name="shrimp", quantity=1.0, unit="lb"),
                Ingredient(name="garlic", quantity=4.0, unit="cloves"),
                Ingredient(name="lemon", quantity=1.0, unit="whole"),
                Ingredient(name="butter", quantity=3.0, unit="tbsp"),
            ],
            instructions="Cook pasta, sauté shrimp with garlic and lemon.",
            servings=4,
            prep_minutes=15,
            cook_minutes=20,
            tags=["dinner", "seafood"],
            category=RecipeCategory.MAIN,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ),
    ]

    nutritions = [
        Nutrition(
            recipe_id="recipe-chicken",
            calories=280.0,
            protein_g=45.0,
            carbs_g=2.0,
            fat_g=10.0,
            fiber_g=0.0,
            sodium_mg=150.0,
            source=NutritionSource.USDA,
            confidence=0.85,
            computed_at=datetime.now(),
        ),
        Nutrition(
            recipe_id="recipe-quinoa",
            calories=220.0,
            protein_g=8.0,
            carbs_g=35.0,
            fat_g=5.0,
            fiber_g=5.0,
            sodium_mg=50.0,
            source=NutritionSource.USDA,
            confidence=0.80,
            computed_at=datetime.now(),
        ),
        Nutrition(
            recipe_id="recipe-pasta",
            calories=450.0,
            protein_g=30.0,
            carbs_g=55.0,
            fat_g=12.0,
            fiber_g=3.0,
            sodium_mg=300.0,
            source=NutritionSource.USDA,
            confidence=0.75,
            computed_at=datetime.now(),
        ),
    ]

    for recipe in recipes:
        await upsert_recipe(recipe)
        await index_recipe_fts(recipe)

    for nutr in nutritions:
        await upsert_nutrition(nutr)

    return recipes
