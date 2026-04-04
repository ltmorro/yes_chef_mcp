"""Meal composition and complement suggestion logic."""

from __future__ import annotations

from yes_chef_mcp.core.db import get_db
from yes_chef_mcp.core.models import (
    ComplementSuggestion,
    ComponentNutrition,
    MacroSummary,
    MacroTarget,
    MealComponent,
    MealComposition,
    RecipeCategory,
)
from yes_chef_mcp.core.recipe_store import get_nutrition, get_recipe
from yes_chef_mcp.core.search import macro_distance_search


async def _get_active_target(member_id: str) -> MacroTarget | None:
    """Fetch the active macro target for a member."""
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM macro_targets WHERE member_id = ? AND is_active = 1",
            (member_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return MacroTarget(
                id=str(row["id"]),
                member_id=str(row["member_id"]),
                name=str(row["name"]),
                calories=float(str(row["calories"])),
                protein_g=float(str(row["protein_g"])),
                carbs_g=float(str(row["carbs_g"])),
                fat_g=float(str(row["fat_g"])),
                is_active=True,
            )


async def _get_named_target(member_id: str, target_name: str) -> MacroTarget | None:
    """Fetch a specific named macro target for a member."""
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM macro_targets WHERE member_id = ? AND name = ?",
            (member_id, target_name),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return MacroTarget(
                id=str(row["id"]),
                member_id=str(row["member_id"]),
                name=str(row["name"]),
                calories=float(str(row["calories"])),
                protein_g=float(str(row["protein_g"])),
                carbs_g=float(str(row["carbs_g"])),
                fat_g=float(str(row["fat_g"])),
                is_active=bool(row["is_active"]),
            )


async def compose_meal(
    components: list[MealComponent],
    member_id: str | None = None,
    target_name: str | None = None,
) -> MealComposition:
    """Compose a meal from multiple recipe components and compute totals.

    If member_id is provided, computes deviation from the member's active target
    (or a specific named target if target_name is given).
    """
    comp_nutritions: list[ComponentNutrition] = []
    total_cal = 0.0
    total_protein = 0.0
    total_carbs = 0.0
    total_fat = 0.0

    for component in components:
        recipe = await get_recipe(component.recipe_id)
        if recipe is None:
            continue

        nutrition = await get_nutrition(component.recipe_id)
        if nutrition is None:
            comp_nutritions.append(
                ComponentNutrition(
                    recipe_id=component.recipe_id,
                    recipe_name=recipe.name,
                    servings=component.servings,
                    macros=MacroSummary(),
                )
            )
            continue

        scaled_cal = nutrition.calories * component.servings
        scaled_protein = nutrition.protein_g * component.servings
        scaled_carbs = nutrition.carbs_g * component.servings
        scaled_fat = nutrition.fat_g * component.servings

        total_cal += scaled_cal
        total_protein += scaled_protein
        total_carbs += scaled_carbs
        total_fat += scaled_fat

        comp_nutritions.append(
            ComponentNutrition(
                recipe_id=component.recipe_id,
                recipe_name=recipe.name,
                servings=component.servings,
                macros=MacroSummary(
                    calories=scaled_cal,
                    protein_g=scaled_protein,
                    carbs_g=scaled_carbs,
                    fat_g=scaled_fat,
                ),
            )
        )

    totals = MacroSummary(
        calories=total_cal,
        protein_g=total_protein,
        carbs_g=total_carbs,
        fat_g=total_fat,
    )

    member_deltas: dict[str, MacroSummary] = {}
    suggestions: list[str] = []

    if member_id:
        target = (
            await _get_named_target(member_id, target_name)
            if target_name
            else await _get_active_target(member_id)
        )
        if target:
            delta = MacroSummary(
                calories=total_cal - target.calories,
                protein_g=total_protein - target.protein_g,
                carbs_g=total_carbs - target.carbs_g,
                fat_g=total_fat - target.fat_g,
            )
            member_deltas[member_id] = delta

            # Generate suggestions
            if delta.protein_g < -5:
                suggestions.append(
                    f"Short {abs(delta.protein_g):.0f}g protein — "
                    "consider adding a high-protein side."
                )
            if delta.calories > 100:
                suggestions.append(
                    f"Over by {delta.calories:.0f} calories — "
                    "consider reducing servings."
                )

    return MealComposition(
        components=comp_nutritions,
        totals=totals,
        member_deltas=member_deltas,
        suggestions=suggestions,
    )


async def suggest_complements(
    existing_recipe_ids: list[str],
    existing_servings: list[float],
    member_id: str,
    complement_category: RecipeCategory = RecipeCategory.SIDE,
    max_results: int = 5,
) -> list[ComplementSuggestion]:
    """Suggest recipes that fill the macro gap for a member.

    Computes the difference between existing meal components and the member's
    active target, then searches for recipes in the complement category that
    best fill that gap.
    """
    target = await _get_active_target(member_id)
    if target is None:
        return []

    # Compute current totals
    components = [
        MealComponent(recipe_id=rid, servings=s)
        for rid, s in zip(existing_recipe_ids, existing_servings, strict=True)
    ]
    current = await compose_meal(components)

    # Compute gap
    gap_cal = target.calories - current.totals.calories
    gap_protein = target.protein_g - current.totals.protein_g
    gap_carbs = target.carbs_g - current.totals.carbs_g
    gap_fat = target.fat_g - current.totals.fat_g

    # Search for recipes near the gap
    results = await macro_distance_search(
        target_calories=max(gap_cal, 0),
        target_protein_g=max(gap_protein, 0),
        target_carbs_g=max(gap_carbs, 0),
        target_fat_g=max(gap_fat, 0),
        category=complement_category,
        max_results=max_results,
        tolerance_pct=50.0,
    )

    suggestions: list[ComplementSuggestion] = []
    for hit in results.hits:
        projected = MacroSummary(
            calories=current.totals.calories + hit.macro_summary.calories,
            protein_g=current.totals.protein_g + hit.macro_summary.protein_g,
            carbs_g=current.totals.carbs_g + hit.macro_summary.carbs_g,
            fat_g=current.totals.fat_g + hit.macro_summary.fat_g,
        )
        deviation = MacroSummary(
            calories=projected.calories - target.calories,
            protein_g=projected.protein_g - target.protein_g,
            carbs_g=projected.carbs_g - target.carbs_g,
            fat_g=projected.fat_g - target.fat_g,
        )
        suggestions.append(
            ComplementSuggestion(
                recipe_id=hit.id,
                recipe_name=hit.name,
                category=hit.category,
                suggested_servings=1.0,
                projected_totals=projected,
                projected_deviation=deviation,
            )
        )

    return suggestions
