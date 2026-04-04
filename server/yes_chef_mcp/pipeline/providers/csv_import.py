"""CSV recipe provider for manual import fallback."""

from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path

from yes_chef_mcp.pipeline.providers.base import (
    RawIngredient,
    RawRecipe,
    RecipeProvider,
)

logger = logging.getLogger(__name__)


class CSVProvider(RecipeProvider):
    """Import recipes from a CSV file.

    Expected columns: name, ingredients, instructions, servings,
    prep_minutes, cook_minutes, tags, category, image_url

    Ingredients are semicolon-separated strings like "2 cups flour; 1 tsp salt".
    Tags are comma-separated.
    """

    def __init__(self, file_path: str) -> None:
        self._path = Path(file_path)

    async def authenticate(self) -> None:
        """Verify the CSV file exists."""
        if not self._path.exists():
            raise FileNotFoundError(f"CSV file not found: {self._path}")

    async def fetch_recipes(
        self, since: datetime | None = None
    ) -> list[RawRecipe]:
        """Parse recipes from the CSV file."""
        if not self._path.exists():
            raise FileNotFoundError(f"CSV file not found: {self._path}")

        recipes: list[RawRecipe] = []

        with self._path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                name = row.get("name", "").strip()
                if not name:
                    continue

                # Parse ingredients
                raw_ingredients: list[RawIngredient] = []
                ingredients_str = row.get("ingredients", "")
                if ingredients_str:
                    for part in ingredients_str.split(";"):
                        part = part.strip()
                        if part:
                            raw_ingredients.append(
                                RawIngredient(name=part, raw_text=part)
                            )

                # Parse tags
                tags_str = row.get("tags", "")
                tags = [t.strip() for t in tags_str.split(",") if t.strip()]

                servings_str = row.get("servings", "1")
                prep_str = row.get("prep_minutes", "")
                cook_str = row.get("cook_minutes", "")

                recipes.append(
                    RawRecipe(
                        external_id=f"csv-{i}",
                        name=name,
                        ingredients=raw_ingredients,
                        instructions=row.get("instructions", ""),
                        servings=int(servings_str) if servings_str else 1,
                        prep_minutes=int(prep_str) if prep_str else None,
                        cook_minutes=int(cook_str) if cook_str else None,
                        tags=tags,
                        category=row.get("category", "").strip() or None,
                        image_url=row.get("image_url", "").strip() or None,
                    )
                )

        logger.info("Parsed %d recipes from CSV: %s", len(recipes), self._path)
        return recipes
