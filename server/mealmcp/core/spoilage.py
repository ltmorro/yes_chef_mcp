"""Spoilage-aware scoring for recipe optimization.

Provides ingredient overlap, perishability, and package-waste scoring so the
optimizer can prefer recipe combinations that share perishable ingredients and
minimize leftover waste from standard package sizes. This is a *tertiary*
objective — calorie and macro deviation remain dominant. Spoilage scoring only
nudges the optimizer when two candidate recipes are otherwise close in
nutritional fit.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

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


# ── Package sizes for waste estimation ────────────────────────────────────
# Maps ingredient keywords to common retail package sizes in a canonical unit.
# Multiple sizes represent the typical options you'd find at a grocery store
# (e.g. pint / quart / half-gallon of milk). The optimizer picks the smallest
# package that satisfies total demand to minimize leftover.


@dataclass(frozen=True, slots=True)
class PackageSpec:
    """A common retail package size for a perishable ingredient."""

    unit: str
    sizes: tuple[float, ...]  # ascending order


# Sizes in the ingredient's most common recipe unit
_PACKAGE_SIZES: dict[str, PackageSpec] = {
    # Dairy — cups
    "milk": PackageSpec(unit="cup", sizes=(2.0, 4.0, 8.0, 16.0)),  # pint/qt/hgal/gal
    "cream": PackageSpec(unit="cup", sizes=(1.0, 2.0)),  # half-pint / pint
    "sour cream": PackageSpec(unit="cup", sizes=(1.0, 2.0)),
    "yogurt": PackageSpec(unit="cup", sizes=(0.75, 4.0)),  # single / quart tub
    "butter": PackageSpec(unit="tbsp", sizes=(8.0, 16.0, 32.0)),  # stick / 2-stick / 4-stick
    "cream cheese": PackageSpec(unit="oz", sizes=(8.0, 16.0)),
    # Protein — lb
    "chicken": PackageSpec(unit="lb", sizes=(1.0, 2.0, 3.0, 5.0)),
    "ground beef": PackageSpec(unit="lb", sizes=(1.0, 2.0, 3.0)),
    "ground turkey": PackageSpec(unit="lb", sizes=(1.0, 2.0)),
    "shrimp": PackageSpec(unit="lb", sizes=(1.0, 2.0)),
    "salmon": PackageSpec(unit="lb", sizes=(0.5, 1.0, 1.5)),
    "pork": PackageSpec(unit="lb", sizes=(1.0, 2.0, 3.0)),
    # Produce — whole units or bunches
    "cilantro": PackageSpec(unit="bunch", sizes=(1.0,)),
    "parsley": PackageSpec(unit="bunch", sizes=(1.0,)),
    "basil": PackageSpec(unit="oz", sizes=(0.75, 2.0)),  # clamshell / bunch
    "spinach": PackageSpec(unit="oz", sizes=(5.0, 10.0, 16.0)),
    "lettuce": PackageSpec(unit="head", sizes=(1.0,)),
    "mushroom": PackageSpec(unit="oz", sizes=(8.0, 16.0)),
    "egg": PackageSpec(unit="whole", sizes=(6.0, 12.0, 18.0)),
}


def _normalize_unit(unit: str | None) -> str:
    """Rough unit normalization for package comparison."""
    if unit is None:
        return ""
    u = unit.strip().lower().rstrip("s")  # cups -> cup, tbsps -> tbsp
    aliases: dict[str, str] = {
        "tablespoon": "tbsp",
        "teaspoon": "tsp",
        "ounce": "oz",
        "pound": "lb",
        "clove": "clove",
    }
    return aliases.get(u, u)


def estimate_package_waste(
    ingredients: list[Ingredient],
    config: SpoilageConfig | None = None,
) -> float:
    """Estimate the fraction of perishable purchases that will go to waste.

    For each perishable ingredient with a known package size, sums the total
    quantity needed across recipes, picks the smallest package that covers the
    demand, and computes the waste fraction. The final score is a weighted
    average across all perishable ingredients, weighted by tier.

    Returns a value in [0.0, 1.0] where 0.0 = no waste, 1.0 = all waste.
    Ingredients without known package sizes or with mismatched units are
    skipped (they fall back to the overlap heuristic).
    """
    if config is None:
        config = SpoilageConfig()

    # Aggregate total quantity per normalized ingredient name
    totals: dict[str, float] = {}
    units: dict[str, str] = {}
    for ing in ingredients:
        key = ing.name.strip().lower()
        if ing.quantity is not None and ing.quantity > 0:
            totals[key] = totals.get(key, 0.0) + ing.quantity
            if key not in units:
                units[key] = _normalize_unit(ing.unit)

    weighted_waste = 0.0
    total_weight = 0.0

    for keyword in sorted(_PACKAGE_SIZES, key=len, reverse=True):
        pkg = _PACKAGE_SIZES[keyword]
        pkg_unit = _normalize_unit(pkg.unit)

        for ing_key, qty in totals.items():
            if keyword not in ing_key:
                continue
            if units.get(ing_key, "") != pkg_unit:
                continue

            profile = classify_ingredient(ing_key)
            multiplier = _tier_multiplier(profile.tier, config)
            if multiplier == 0.0:
                continue

            # Find smallest package that covers the need
            chosen_size = pkg.sizes[-1]  # default to largest
            for size in pkg.sizes:
                if size >= qty:
                    chosen_size = size
                    break

            waste_fraction = (chosen_size - qty) / chosen_size if chosen_size > 0 else 0.0
            waste_fraction = max(0.0, min(1.0, waste_fraction))

            weighted_waste += waste_fraction * multiplier
            total_weight += multiplier

            # Remove so we don't double-count
            del totals[ing_key]
            break

    if total_weight == 0.0:
        return 0.0
    return weighted_waste / total_weight


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
