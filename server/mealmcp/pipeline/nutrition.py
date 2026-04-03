"""Nutrition enrichment via USDA FoodData Central and Nutritionix APIs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

from mealmcp.core.models import Ingredient, Nutrition, NutritionSource

logger = logging.getLogger(__name__)

USDA_API_BASE = "https://api.nal.usda.gov/fdc/v1"


@dataclass(frozen=True, slots=True)
class NutrientHit:
    """A single nutrient match from a food database lookup."""

    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    sodium_mg: float
    confidence: float


class NutritionEnricher:
    """Enriches recipes with nutrition data from external APIs."""

    def __init__(
        self,
        usda_api_key: str | None = None,
        nutritionix_app_id: str | None = None,
        nutritionix_app_key: str | None = None,
    ) -> None:
        self._usda_key = usda_api_key
        self._nutritionix_app_id = nutritionix_app_id
        self._nutritionix_app_key = nutritionix_app_key

    async def enrich_recipe(
        self,
        recipe_id: str,
        ingredients: list[Ingredient],
        servings: int,
    ) -> Nutrition | None:
        """Compute per-serving nutrition for a recipe.

        Looks up each ingredient against USDA, falls back to Nutritionix.
        Returns None if no ingredients could be matched.
        """
        total_cal = 0.0
        total_protein = 0.0
        total_carbs = 0.0
        total_fat = 0.0
        total_fiber = 0.0
        total_sodium = 0.0
        matched = 0
        total_confidence = 0.0

        for ingredient in ingredients:
            hit = await self._lookup_ingredient(ingredient)
            if hit is None:
                continue

            qty = ingredient.quantity or 1.0
            total_cal += hit.calories * qty
            total_protein += hit.protein_g * qty
            total_carbs += hit.carbs_g * qty
            total_fat += hit.fat_g * qty
            total_fiber += hit.fiber_g * qty
            total_sodium += hit.sodium_mg * qty
            total_confidence += hit.confidence
            matched += 1

        if matched == 0:
            return None

        per_serving = max(servings, 1)
        avg_confidence = total_confidence / matched

        return Nutrition(
            recipe_id=recipe_id,
            calories=round(total_cal / per_serving, 1),
            protein_g=round(total_protein / per_serving, 1),
            carbs_g=round(total_carbs / per_serving, 1),
            fat_g=round(total_fat / per_serving, 1),
            fiber_g=round(total_fiber / per_serving, 1),
            sodium_mg=round(total_sodium / per_serving, 1),
            source=NutritionSource.USDA,
            confidence=round(avg_confidence, 2),
            computed_at=datetime.now(),
        )

    async def _lookup_ingredient(self, ingredient: Ingredient) -> NutrientHit | None:
        """Look up a single ingredient. Tries USDA first, then Nutritionix."""
        hit = await self._lookup_usda(ingredient.name)
        if hit is not None:
            return hit

        hit = await self._lookup_nutritionix(ingredient.name)
        return hit

    async def _lookup_usda(self, query: str) -> NutrientHit | None:
        """Search USDA FoodData Central for a food item."""
        if not self._usda_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{USDA_API_BASE}/foods/search",
                    params={
                        "api_key": self._usda_key,
                        "query": query,
                        "dataType": "Foundation,SR Legacy",
                        "pageSize": 1,
                    },
                )
                response.raise_for_status()
                data = response.json()

                foods: list[dict[str, object]] = data.get("foods", [])
                if not foods:
                    return None

                food = foods[0]
                nutrients: list[dict[str, object]] = food.get("foodNutrients", [])  # type: ignore[assignment]

                return _parse_usda_nutrients(nutrients)

        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.debug("USDA lookup failed for %r: %s", query, exc)
            return None

    async def _lookup_nutritionix(self, query: str) -> NutrientHit | None:
        """Search Nutritionix for a food item."""
        if not self._nutritionix_app_id or not self._nutritionix_app_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://trackapi.nutritionix.com/v2/natural/nutrients",
                    headers={
                        "x-app-id": self._nutritionix_app_id,
                        "x-app-key": self._nutritionix_app_key,
                    },
                    json={"query": query},
                )
                response.raise_for_status()
                data = response.json()

                foods: list[dict[str, object]] = data.get("foods", [])
                if not foods:
                    return None

                food = foods[0]
                return NutrientHit(
                    calories=float(str(food.get("nf_calories", 0))),
                    protein_g=float(str(food.get("nf_protein", 0))),
                    carbs_g=float(str(food.get("nf_total_carbohydrate", 0))),
                    fat_g=float(str(food.get("nf_total_fat", 0))),
                    fiber_g=float(str(food.get("nf_dietary_fiber", 0))),
                    sodium_mg=float(str(food.get("nf_sodium", 0))),
                    confidence=0.7,
                )

        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.debug("Nutritionix lookup failed for %r: %s", query, exc)
            return None


# USDA nutrient IDs
_USDA_NUTRIENT_MAP: dict[int, str] = {
    1008: "calories",
    1003: "protein_g",
    1005: "carbs_g",
    1004: "fat_g",
    1079: "fiber_g",
    1093: "sodium_mg",
}


def _parse_usda_nutrients(nutrients: list[dict[str, object]]) -> NutrientHit:
    """Parse USDA nutrient response into a NutrientHit."""
    values: dict[str, float] = {
        "calories": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
        "sodium_mg": 0.0,
    }

    for n in nutrients:
        nutrient_id = int(str(n.get("nutrientId", 0)))
        field_name = _USDA_NUTRIENT_MAP.get(nutrient_id)
        if field_name:
            values[field_name] = float(str(n.get("value", 0)))

    return NutrientHit(
        calories=values["calories"],
        protein_g=values["protein_g"],
        carbs_g=values["carbs_g"],
        fat_g=values["fat_g"],
        fiber_g=values["fiber_g"],
        sodium_mg=values["sodium_mg"],
        confidence=0.8,
    )
