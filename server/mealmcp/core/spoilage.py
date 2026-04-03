"""Spoilage-aware scoring for recipe optimization.

Provides ingredient overlap and perishability scoring so the optimizer
can prefer recipe combinations that share perishable ingredients, reducing
food waste. This is a *tertiary* objective — calorie and macro deviation
remain dominant. Spoilage scoring only nudges the optimizer when two
candidate recipes are otherwise close in nutritional fit.
"""

from __future__ import annotations

from collections import Counter

from mealmcp.core.models import (
    Ingredient,
    PerishabilityTier,
    SpoilageConfig,
    SpoilageProfile,
)

# ── Default perishability profiles ────────────────────────────────────────
# Keyword-based lookup, similar to grocery._guess_category.
# Keys are lowercased substrings matched against ingredient names.

_PERISHABILITY_KEYWORDS: dict[str, tuple[PerishabilityTier, int]] = {
    # HIGH tier (1-4 days)
    "basil": (PerishabilityTier.HIGH, 3),
    "cilantro": (PerishabilityTier.HIGH, 3),
    "parsley": (PerishabilityTier.HIGH, 4),
    "dill": (PerishabilityTier.HIGH, 3),
    "mint": (PerishabilityTier.HIGH, 3),
    "berries": (PerishabilityTier.HIGH, 3),
    "strawberr": (PerishabilityTier.HIGH, 3),
    "raspberr": (PerishabilityTier.HIGH, 2),
    "blueberr": (PerishabilityTier.HIGH, 4),
    "fish": (PerishabilityTier.HIGH, 2),
    "fresh salmon": (PerishabilityTier.HIGH, 2),
    "scallop": (PerishabilityTier.HIGH, 2),
    "avocado": (PerishabilityTier.HIGH, 3),
    "lettuce": (PerishabilityTier.HIGH, 4),
    "spinach": (PerishabilityTier.HIGH, 4),
    "arugula": (PerishabilityTier.HIGH, 3),
    "bean sprout": (PerishabilityTier.HIGH, 2),
    # MEDIUM tier (5-10 days)
    "milk": (PerishabilityTier.MEDIUM, 7),
    "yogurt": (PerishabilityTier.MEDIUM, 10),
    "cream cheese": (PerishabilityTier.MEDIUM, 10),
    "sour cream": (PerishabilityTier.MEDIUM, 10),
    "cream": (PerishabilityTier.MEDIUM, 7),
    "butter": (PerishabilityTier.MEDIUM, 10),
    "chicken": (PerishabilityTier.MEDIUM, 5),
    "ground beef": (PerishabilityTier.MEDIUM, 5),
    "ground turkey": (PerishabilityTier.MEDIUM, 5),
    "pork": (PerishabilityTier.MEDIUM, 5),
    "shrimp": (PerishabilityTier.MEDIUM, 5),
    "tofu": (PerishabilityTier.MEDIUM, 7),
    "mushroom": (PerishabilityTier.MEDIUM, 7),
    "broccoli": (PerishabilityTier.MEDIUM, 7),
    "bell pepper": (PerishabilityTier.MEDIUM, 7),
    "zucchini": (PerishabilityTier.MEDIUM, 7),
    "cucumber": (PerishabilityTier.MEDIUM, 7),
    "tomato": (PerishabilityTier.MEDIUM, 7),
    "celery": (PerishabilityTier.MEDIUM, 10),
    "green onion": (PerishabilityTier.MEDIUM, 7),
    "kale": (PerishabilityTier.MEDIUM, 7),
    # LOW tier (11-21 days)
    "egg": (PerishabilityTier.LOW, 21),
    "cheese": (PerishabilityTier.LOW, 21),
    "parmesan": (PerishabilityTier.LOW, 21),
    "cheddar": (PerishabilityTier.LOW, 21),
    "mozzarella": (PerishabilityTier.LOW, 14),
    "carrot": (PerishabilityTier.LOW, 21),
    "potato": (PerishabilityTier.LOW, 21),
    "sweet potato": (PerishabilityTier.LOW, 21),
    "onion": (PerishabilityTier.LOW, 21),
    "garlic": (PerishabilityTier.LOW, 21),
    "ginger": (PerishabilityTier.LOW, 14),
    "cabbage": (PerishabilityTier.LOW, 14),
    "apple": (PerishabilityTier.LOW, 21),
    "lemon": (PerishabilityTier.LOW, 21),
    "lime": (PerishabilityTier.LOW, 14),
    "orange": (PerishabilityTier.LOW, 14),
    # STABLE tier (shelf-stable) — not exhaustive, used as fallback
    "canned": (PerishabilityTier.STABLE, 365),
    "rice": (PerishabilityTier.STABLE, 365),
    "pasta": (PerishabilityTier.STABLE, 365),
    "quinoa": (PerishabilityTier.STABLE, 365),
    "flour": (PerishabilityTier.STABLE, 180),
    "sugar": (PerishabilityTier.STABLE, 730),
    "honey": (PerishabilityTier.STABLE, 730),
    "soy sauce": (PerishabilityTier.STABLE, 365),
    "vinegar": (PerishabilityTier.STABLE, 730),
    "oil": (PerishabilityTier.STABLE, 365),
    "dried": (PerishabilityTier.STABLE, 365),
    "frozen": (PerishabilityTier.STABLE, 180),
    "broth": (PerishabilityTier.STABLE, 365),
    "stock": (PerishabilityTier.STABLE, 365),
    "bread crumb": (PerishabilityTier.STABLE, 180),
    "tortilla": (PerishabilityTier.STABLE, 30),
    "noodle": (PerishabilityTier.STABLE, 365),
    "oat": (PerishabilityTier.STABLE, 365),
    "bean": (PerishabilityTier.STABLE, 365),
    "lentil": (PerishabilityTier.STABLE, 365),
    "nut": (PerishabilityTier.STABLE, 180),
    "seed": (PerishabilityTier.STABLE, 180),
    "spice": (PerishabilityTier.STABLE, 365),
    "salt": (PerishabilityTier.STABLE, 3650),
    "pepper": (PerishabilityTier.STABLE, 365),
}


def classify_ingredient(name: str) -> SpoilageProfile:
    """Classify an ingredient's perishability using keyword matching.

    Longest-match-first so "cream cheese" beats "cream" and "green onion"
    beats "onion".
    """
    lower = name.strip().lower()

    # Sort by keyword length descending for longest-match-first
    for keyword in sorted(_PERISHABILITY_KEYWORDS, key=len, reverse=True):
        if keyword in lower:
            tier, shelf_days = _PERISHABILITY_KEYWORDS[keyword]
            return SpoilageProfile(
                ingredient_name=lower,
                tier=tier,
                shelf_life_days=shelf_days,
            )

    # Default: assume stable (pantry item or unrecognised)
    return SpoilageProfile(
        ingredient_name=lower,
        tier=PerishabilityTier.STABLE,
        shelf_life_days=365,
    )


def _tier_multiplier(tier: PerishabilityTier, config: SpoilageConfig) -> float:
    """Get the scoring multiplier for a perishability tier."""
    return {
        PerishabilityTier.HIGH: config.high_tier_multiplier,
        PerishabilityTier.MEDIUM: config.medium_tier_multiplier,
        PerishabilityTier.LOW: config.low_tier_multiplier,
        PerishabilityTier.STABLE: config.stable_tier_multiplier,
    }[tier]


def ingredient_overlap_bonus(
    recipe_ingredients: list[list[Ingredient]],
    config: SpoilageConfig | None = None,
) -> float:
    """Score how well a set of recipes shares perishable ingredients.

    Higher is better — recipes that reuse the same perishable items get
    a positive bonus. The bonus is weighted by perishability tier so
    sharing milk (MEDIUM) matters more than sharing rice (STABLE).

    Args:
        recipe_ingredients: list of ingredient lists, one per recipe in
            the candidate set.
        config: tuning knobs. Uses defaults if None.

    Returns:
        A non-negative bonus value. 0.0 when there is no meaningful
        overlap among perishable ingredients.
    """
    if config is None:
        config = SpoilageConfig()

    if len(recipe_ingredients) < 2:
        return 0.0

    # Count how many recipes use each normalized ingredient
    ingredient_recipe_count: Counter[str] = Counter()
    ingredient_profiles: dict[str, SpoilageProfile] = {}

    for ingredients in recipe_ingredients:
        # Deduplicate within a single recipe
        seen_in_recipe: set[str] = set()
        for ing in ingredients:
            key = ing.name.strip().lower()
            if key in seen_in_recipe:
                continue
            seen_in_recipe.add(key)

            ingredient_recipe_count[key] += 1
            if key not in ingredient_profiles:
                ingredient_profiles[key] = classify_ingredient(ing.name)

    bonus = 0.0
    for key, count in ingredient_recipe_count.items():
        if count < 2:
            continue  # No overlap

        profile = ingredient_profiles[key]
        multiplier = _tier_multiplier(profile.tier, config)
        if multiplier == 0.0:
            continue

        # Bonus scales with (count - 1) so 3 recipes sharing = 2x bonus of 2 recipes
        bonus += config.overlap_bonus_per_shared * (count - 1) * multiplier

    return bonus


def plan_spoilage_penalty(
    plan_ingredient_lists: list[list[Ingredient]],
    config: SpoilageConfig | None = None,
) -> float:
    """Compute a penalty for perishable ingredients used in only one recipe.

    This identifies "orphaned" perishables — ingredients bought for a single
    recipe in the plan that are likely to spoil before being used again.

    Args:
        plan_ingredient_lists: all ingredient lists across the full plan
            (one list per meal slot).
        config: tuning knobs.

    Returns:
        A non-negative penalty value. 0.0 when all perishable ingredients
        appear in multiple recipes.
    """
    if config is None:
        config = SpoilageConfig()

    ingredient_recipe_count: Counter[str] = Counter()
    ingredient_profiles: dict[str, SpoilageProfile] = {}

    for ingredients in plan_ingredient_lists:
        seen: set[str] = set()
        for ing in ingredients:
            key = ing.name.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            ingredient_recipe_count[key] += 1
            if key not in ingredient_profiles:
                ingredient_profiles[key] = classify_ingredient(ing.name)

    penalty = 0.0
    for key, count in ingredient_recipe_count.items():
        if count > 1:
            continue  # Used in multiple recipes — no penalty

        profile = ingredient_profiles[key]
        multiplier = _tier_multiplier(profile.tier, config)
        if multiplier == 0.0:
            continue

        # Penalty for singleton perishables
        penalty += config.overlap_bonus_per_shared * multiplier

    return penalty
