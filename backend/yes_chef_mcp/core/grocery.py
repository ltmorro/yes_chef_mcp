"""Grocery list generation from meal plans."""

from __future__ import annotations

from collections import defaultdict

from yes_chef_mcp.core.models import GroceryItem, GroceryList
from yes_chef_mcp.core.planner import get_meal_slots
from yes_chef_mcp.core.recipe_store import get_recipe

# Common pantry items to exclude when exclude_pantry=True
PANTRY_ITEMS = frozenset({
    "salt", "pepper", "black pepper", "olive oil", "vegetable oil",
    "cooking spray", "water", "ice", "oil", "canola oil", "nonstick spray",
    "cooking oil", "kosher salt", "sea salt", "table salt",
})


def _normalize_ingredient_name(name: str) -> str:
    """Normalize ingredient name for merging."""
    return name.strip().lower()


async def generate_grocery_list(
    plan_id: str,
    merge_similar: bool = True,
    exclude_pantry: bool = True,
) -> GroceryList:
    """Generate a consolidated grocery list from all recipes in a meal plan.

    Sums quantities across recipes, groups by ingredient category,
    and optionally merges similar ingredients and excludes pantry staples.
    """
    slots = await get_meal_slots(plan_id)

    # Aggregate ingredients across all slots
    # Key: normalized ingredient name → accumulated data
    aggregated: dict[str, _AggItem] = defaultdict(_AggItem)

    for slot in slots:
        recipe = await get_recipe(slot.recipe_id)
        if recipe is None:
            continue

        # Compute total servings multiplier
        if slot.member_servings:
            total_servings = sum(slot.member_servings.values())
        else:
            total_servings = slot.servings

        scale = total_servings / max(recipe.servings, 1)

        for ing in recipe.ingredients:
            key = _normalize_ingredient_name(ing.name)

            if exclude_pantry and key in PANTRY_ITEMS:
                continue

            item = aggregated[key]
            item.name = ing.name  # Keep original casing from last seen
            if ing.quantity is not None:
                item.quantity += ing.quantity * scale
            item.unit = item.unit or ing.unit
            item.recipe_sources.add(recipe.name)

    items = [
        GroceryItem(
            name=agg.name,
            quantity=round(agg.quantity, 2),
            unit=agg.unit,
            category=_guess_category(agg.name),
            recipe_sources=sorted(agg.recipe_sources),
        )
        for agg in aggregated.values()
    ]

    items.sort(key=lambda i: (i.category, i.name))

    return GroceryList(plan_id=plan_id, items=items)


class _AggItem:
    """Mutable accumulator for ingredient aggregation."""

    __slots__ = ("name", "quantity", "unit", "recipe_sources")

    def __init__(self) -> None:
        self.name: str = ""
        self.quantity: float = 0.0
        self.unit: str | None = None
        self.recipe_sources: set[str] = set()


# Simple keyword-based category guessing
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "produce": [
        "lettuce", "tomato", "onion", "garlic", "pepper", "carrot",
        "celery", "potato", "broccoli", "spinach", "kale", "mushroom",
        "avocado", "lemon", "lime", "orange", "apple", "banana",
        "cilantro", "parsley", "basil", "ginger", "cucumber", "zucchini",
    ],
    "protein": [
        "chicken", "beef", "pork", "turkey", "salmon", "shrimp", "fish",
        "tofu", "tempeh", "sausage", "bacon", "lamb", "ground",
    ],
    "dairy": [
        "milk", "cheese", "yogurt", "butter", "cream", "sour cream",
        "parmesan", "mozzarella", "cheddar", "egg", "eggs",
    ],
    "grain": [
        "rice", "pasta", "bread", "flour", "tortilla", "noodle",
        "quinoa", "oat", "couscous", "cereal",
    ],
    "canned": [
        "canned", "tomato sauce", "tomato paste", "broth", "stock",
        "coconut milk", "beans",
    ],
    "spice": [
        "cumin", "paprika", "oregano", "thyme", "cinnamon", "chili powder",
        "curry", "turmeric", "cayenne", "nutmeg",
    ],
    "condiment": [
        "soy sauce", "vinegar", "mustard", "ketchup", "mayo", "hot sauce",
        "worcestershire", "honey", "maple syrup", "sriracha",
    ],
}


def _guess_category(ingredient_name: str) -> str:
    """Guess the store aisle category from ingredient name."""
    lower = ingredient_name.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in lower:
                return category
    return "other"
