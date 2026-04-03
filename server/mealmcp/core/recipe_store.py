"""CRUD operations for recipes, nutrition, and embeddings."""

from __future__ import annotations

import json
from datetime import datetime

import aiosqlite

from mealmcp.core.db import get_db
from mealmcp.core.models import (
    Ingredient,
    Nutrition,
    NutritionSource,
    Recipe,
    RecipeCategory,
    RecipeSource,
)


def _row_to_recipe(row: aiosqlite.Row) -> Recipe:
    """Convert a database row to a Recipe dataclass."""
    raw_ingredients = json.loads(str(row["ingredients"]))
    ingredients = [
        Ingredient(
            name=ing["name"],
            quantity=ing.get("quantity"),
            unit=ing.get("unit"),
            raw_text=ing.get("raw_text", ""),
            sub_recipe_id=ing.get("sub_recipe_id"),
        )
        for ing in raw_ingredients
    ]

    raw_tags = json.loads(str(row["tags"]))
    category_val = row["category"]
    category = RecipeCategory(str(category_val)) if category_val else None

    created_str = row["created_at"]
    updated_str = row["updated_at"]

    return Recipe(
        id=str(row["id"]),
        family_id=str(row["family_id"]),
        name=str(row["name"]),
        source=RecipeSource(str(row["source"])),
        ingredients=ingredients,
        instructions=str(row["instructions"]),
        servings=int(str(row["servings"])),
        prep_minutes=int(str(row["prep_minutes"])) if row["prep_minutes"] is not None else None,
        cook_minutes=int(str(row["cook_minutes"])) if row["cook_minutes"] is not None else None,
        tags=[str(t) for t in raw_tags],
        category=category,
        image_url=str(row["image_url"]) if row["image_url"] else None,
        created_at=datetime.fromisoformat(str(created_str)) if created_str else None,
        updated_at=datetime.fromisoformat(str(updated_str)) if updated_str else None,
    )


def _row_to_nutrition(row: aiosqlite.Row) -> Nutrition:
    """Convert a database row to a Nutrition dataclass."""
    computed_str = row["computed_at"]
    return Nutrition(
        recipe_id=str(row["recipe_id"]),
        calories=float(str(row["calories"])),
        protein_g=float(str(row["protein_g"])),
        carbs_g=float(str(row["carbs_g"])),
        fat_g=float(str(row["fat_g"])),
        fiber_g=float(str(row["fiber_g"])),
        sodium_mg=float(str(row["sodium_mg"])),
        source=NutritionSource(str(row["source"])),
        confidence=float(str(row["confidence"])),
        computed_at=datetime.fromisoformat(str(computed_str)) if computed_str else None,
    )


async def upsert_recipe(recipe: Recipe) -> None:
    """Insert or update a recipe."""
    ingredients_json = json.dumps(
        [
            {
                "name": ing.name,
                "quantity": ing.quantity,
                "unit": ing.unit,
                "raw_text": ing.raw_text,
                "sub_recipe_id": ing.sub_recipe_id,
            }
            for ing in recipe.ingredients
        ]
    )
    tags_json = json.dumps(recipe.tags)

    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO recipes (
                id, family_id, name, source, ingredients, instructions,
                servings, prep_minutes, cook_minutes, tags, category,
                image_url, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                source=excluded.source,
                ingredients=excluded.ingredients,
                instructions=excluded.instructions,
                servings=excluded.servings,
                prep_minutes=excluded.prep_minutes,
                cook_minutes=excluded.cook_minutes,
                tags=excluded.tags,
                category=excluded.category,
                image_url=excluded.image_url,
                updated_at=excluded.updated_at
            """,
            (
                recipe.id,
                recipe.family_id,
                recipe.name,
                recipe.source.value,
                ingredients_json,
                recipe.instructions,
                recipe.servings,
                recipe.prep_minutes,
                recipe.cook_minutes,
                tags_json,
                recipe.category.value if recipe.category else None,
                recipe.image_url,
                recipe.created_at.isoformat() if recipe.created_at else None,
                recipe.updated_at.isoformat() if recipe.updated_at else None,
            ),
        )


async def get_recipe(recipe_id: str) -> Recipe | None:
    """Fetch a single recipe by ID."""
    async with get_db() as db:
        async with db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return _row_to_recipe(row)


async def list_recipes(
    family_id: str | None = None,
    category: RecipeCategory | None = None,
    tags: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Recipe]:
    """List recipes with optional filters."""
    conditions: list[str] = []
    params: list[str | int] = []

    if family_id:
        conditions.append("r.family_id = ?")
        params.append(family_id)
    if category:
        conditions.append("r.category = ?")
        params.append(category.value)
    if tags:
        placeholders = ",".join("?" for _ in tags)
        conditions.append(
            f"""EXISTS (
                SELECT 1 FROM json_each(r.tags) AS jt
                WHERE jt.value IN ({placeholders})
            )"""
        )
        params.extend(tags)

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT r.* FROM recipes r{where} ORDER BY r.name LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    async with get_db() as db:
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()

    return [_row_to_recipe(row) for row in rows]


async def delete_recipe(recipe_id: str) -> bool:
    """Delete a recipe. Returns True if deleted."""
    async with get_db() as db:
        await db.execute("DELETE FROM nutrition WHERE recipe_id = ?", (recipe_id,))
        cursor = await db.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        return cursor.rowcount > 0


# ── Nutrition ─────────────────────────────────────────────────────────────


async def upsert_nutrition(nutrition: Nutrition) -> None:
    """Insert or update nutrition data for a recipe."""
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO nutrition (
                recipe_id, calories, protein_g, carbs_g, fat_g,
                fiber_g, sodium_mg, source, confidence, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(recipe_id) DO UPDATE SET
                calories=excluded.calories,
                protein_g=excluded.protein_g,
                carbs_g=excluded.carbs_g,
                fat_g=excluded.fat_g,
                fiber_g=excluded.fiber_g,
                sodium_mg=excluded.sodium_mg,
                source=excluded.source,
                confidence=excluded.confidence,
                computed_at=excluded.computed_at
            """,
            (
                nutrition.recipe_id,
                nutrition.calories,
                nutrition.protein_g,
                nutrition.carbs_g,
                nutrition.fat_g,
                nutrition.fiber_g,
                nutrition.sodium_mg,
                nutrition.source.value,
                nutrition.confidence,
                nutrition.computed_at.isoformat() if nutrition.computed_at else None,
            ),
        )


async def get_nutrition(recipe_id: str) -> Nutrition | None:
    """Fetch nutrition data for a recipe."""
    async with get_db() as db:
        async with db.execute("SELECT * FROM nutrition WHERE recipe_id = ?", (recipe_id,)) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return _row_to_nutrition(row)


async def get_nutrition_batch(recipe_ids: list[str]) -> dict[str, Nutrition]:
    """Fetch nutrition data for multiple recipes."""
    if not recipe_ids:
        return {}
    placeholders = ",".join("?" for _ in recipe_ids)
    async with get_db() as db:
        async with db.execute(
            f"SELECT * FROM nutrition WHERE recipe_id IN ({placeholders})",
            recipe_ids,
        ) as cursor:
            rows = await cursor.fetchall()
    return {str(row["recipe_id"]): _row_to_nutrition(row) for row in rows}


# ── FTS Indexing ──────────────────────────────────────────────────────────


async def index_recipe_fts(recipe: Recipe) -> None:
    """Index a recipe for full-text search."""
    ingredient_names = " ".join(ing.name for ing in recipe.ingredients)
    async with get_db() as db:
        # Delete existing entry
        await db.execute(
            "DELETE FROM recipes_fts WHERE recipe_id = ?",
            (recipe.id,),
        )
        await db.execute(
            "INSERT INTO recipes_fts (recipe_id, name, ingredient_names) VALUES (?, ?, ?)",
            (recipe.id, recipe.name, ingredient_names),
        )


# ── Vector Embeddings ────────────────────────────────────────────────────


async def upsert_embedding(recipe_id: str, embedding: list[float]) -> None:
    """Store or update a recipe embedding in the vec_recipes table."""
    import struct

    vec_blob = struct.pack(f"{len(embedding)}f", *embedding)
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO vec_recipes (recipe_id, embedding)
            VALUES (?, ?)
            ON CONFLICT(recipe_id) DO UPDATE SET embedding=excluded.embedding
            """,
            (recipe_id, vec_blob),
        )


# ── Tags & Categories ────────────────────────────────────────────────────


async def list_all_tags(family_id: str | None = None) -> list[str]:
    """List all unique tags across recipes."""
    condition = " WHERE r.family_id = ?" if family_id else ""
    params: list[str] = [family_id] if family_id else []

    query = f"""
        SELECT DISTINCT jt.value AS tag
        FROM recipes r, json_each(r.tags) AS jt
        {condition}
        ORDER BY tag
    """

    async with get_db() as db:
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
    return [str(row["tag"]) for row in rows]


async def list_all_categories(family_id: str | None = None) -> list[str]:
    """List all unique categories across recipes."""
    condition = " WHERE family_id = ?" if family_id else ""
    params: list[str] = [family_id] if family_id else []

    async with get_db() as db:
        async with db.execute(
            f"SELECT DISTINCT category FROM recipes{condition} "
            "WHERE category IS NOT NULL ORDER BY category",
            params,
        ) as cursor:
            rows = await cursor.fetchall()
    return [str(row["category"]) for row in rows]
