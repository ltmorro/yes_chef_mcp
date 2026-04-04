"""Mealie recipe provider.

Connects to a self-hosted Mealie instance via its REST API.
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

from yes_chef_mcp.pipeline.providers.base import (
    RawIngredient,
    RawRecipe,
    RecipeProvider,
)

logger = logging.getLogger(__name__)


class MealieProvider(RecipeProvider):
    """Recipe provider for Mealie (self-hosted)."""

    def __init__(self, base_url: str, api_token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token
        self._client: httpx.AsyncClient | None = None

    async def authenticate(self) -> None:
        """Verify connectivity with Mealie."""
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {self._api_token}"},
            timeout=30.0,
        )
        response = await self._client.get("/api/about")
        response.raise_for_status()
        logger.info("Mealie authentication successful")

    async def fetch_recipes(
        self, since: datetime | None = None
    ) -> list[RawRecipe]:
        """Fetch recipes from Mealie."""
        if self._client is None:
            await self.authenticate()

        assert self._client is not None

        recipes: list[RawRecipe] = []
        page = 1
        per_page = 50

        while True:
            response = await self._client.get(
                "/api/recipes",
                params={"page": page, "perPage": per_page},
            )
            response.raise_for_status()
            data = response.json()

            items: list[dict[str, object]] = data.get("items", [])
            if not items:
                break

            for item in items:
                recipe_id = str(item.get("id", ""))
                # Fetch full recipe detail
                detail_resp = await self._client.get(f"/api/recipes/{recipe_id}")
                if detail_resp.status_code != 200:
                    continue
                detail: dict[str, object] = detail_resp.json()

                updated_str = str(detail.get("dateUpdated", ""))
                updated_at = (
                    datetime.fromisoformat(updated_str) if updated_str else None
                )

                if since and updated_at and updated_at < since:
                    continue

                raw_ingredients: list[RawIngredient] = []
                for ing in detail.get("recipeIngredient", []):  # type: ignore[union-attr]
                    if isinstance(ing, dict):
                        note = str(ing.get("note", ""))
                        food_data = ing.get("food")
                        food_name = (
                            str(food_data.get("name", note))  # type: ignore[union-attr]
                            if isinstance(food_data, dict)
                            else note
                        )
                        qty_val = ing.get("quantity")
                        quantity = float(str(qty_val)) if qty_val is not None else None
                        unit_data = ing.get("unit")
                        unit = (
                            str(unit_data.get("name", ""))  # type: ignore[union-attr]
                            if isinstance(unit_data, dict)
                            else None
                        )
                        raw_ingredients.append(
                            RawIngredient(
                                name=food_name,
                                quantity=quantity,
                                unit=unit,
                                raw_text=str(ing.get("display", note)),
                            )
                        )

                raw_tags: list[str] = []
                tag_list = detail.get("tags", [])
                if isinstance(tag_list, list):
                    for t in tag_list:
                        if isinstance(t, dict):
                            raw_tags.append(str(t.get("name", "")))
                        elif isinstance(t, str):
                            raw_tags.append(t)

                prep_time = detail.get("prepTime")
                cook_time = detail.get("cookTime")

                recipes.append(
                    RawRecipe(
                        external_id=recipe_id,
                        name=str(detail.get("name", "")),
                        ingredients=raw_ingredients,
                        instructions=str(detail.get("recipeInstructions", "")),
                        servings=int(str(detail.get("recipeYield", 1))),
                        prep_minutes=(
                            int(str(prep_time)) if prep_time is not None else None
                        ),
                        cook_minutes=(
                            int(str(cook_time)) if cook_time is not None else None
                        ),
                        tags=raw_tags,
                        image_url=str(detail.get("image", "")),
                        updated_at=updated_at,
                    )
                )

            page += 1

        logger.info("Fetched %d recipes from Mealie", len(recipes))
        return recipes
