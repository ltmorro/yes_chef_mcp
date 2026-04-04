"""Tests for spoilage scoring module."""

from __future__ import annotations

from yes_chef_mcp.core.models import Ingredient, PerishabilityTier, SpoilageConfig
from yes_chef_mcp.core.spoilage import (
    classify_ingredient,
    estimate_package_waste,
    ingredient_overlap_bonus,
    plan_spoilage_penalty,
)

# ── classify_ingredient ──────────────────────────────────────────────────


class TestClassifyIngredient:
    def test_high_tier_fresh_herb(self) -> None:
        profile = classify_ingredient("fresh basil")
        assert profile.tier == PerishabilityTier.HIGH
        assert profile.shelf_life_days == 3

    def test_medium_tier_dairy(self) -> None:
        profile = classify_ingredient("whole milk")
        assert profile.tier == PerishabilityTier.MEDIUM
        assert profile.shelf_life_days == 7

    def test_low_tier_root_vegetable(self) -> None:
        profile = classify_ingredient("carrot")
        assert profile.tier == PerishabilityTier.LOW
        assert profile.shelf_life_days == 21

    def test_stable_tier_pantry(self) -> None:
        profile = classify_ingredient("quinoa")
        assert profile.tier == PerishabilityTier.STABLE

    def test_unknown_defaults_to_stable(self) -> None:
        profile = classify_ingredient("xanthan gum")
        assert profile.tier == PerishabilityTier.STABLE
        assert profile.shelf_life_days == 365

    def test_longest_match_wins(self) -> None:
        """'cream cheese' should match before 'cream'."""
        profile = classify_ingredient("cream cheese")
        assert profile.tier == PerishabilityTier.MEDIUM
        assert profile.shelf_life_days == 10

    def test_green_onion_vs_onion(self) -> None:
        """'green onion' is MEDIUM; plain 'onion' is LOW."""
        green = classify_ingredient("green onion")
        assert green.tier == PerishabilityTier.MEDIUM

        plain = classify_ingredient("yellow onion")
        assert plain.tier == PerishabilityTier.LOW


# ── ingredient_overlap_bonus ─────────────────────────────────────────────


class TestIngredientOverlapBonus:
    def test_no_overlap_returns_zero(self) -> None:
        lists = [
            [Ingredient(name="chicken breast")],
            [Ingredient(name="quinoa")],
        ]
        assert ingredient_overlap_bonus(lists) == 0.0

    def test_single_recipe_returns_zero(self) -> None:
        lists = [[Ingredient(name="milk"), Ingredient(name="butter")]]
        assert ingredient_overlap_bonus(lists) == 0.0

    def test_shared_perishable_gives_bonus(self) -> None:
        lists = [
            [Ingredient(name="milk"), Ingredient(name="flour")],
            [Ingredient(name="milk"), Ingredient(name="sugar")],
        ]
        bonus = ingredient_overlap_bonus(lists)
        assert bonus > 0.0

    def test_stable_overlap_ignored(self) -> None:
        """Sharing shelf-stable ingredients should not produce a bonus."""
        lists = [
            [Ingredient(name="rice"), Ingredient(name="soy sauce")],
            [Ingredient(name="rice"), Ingredient(name="vinegar")],
        ]
        bonus = ingredient_overlap_bonus(lists)
        assert bonus == 0.0

    def test_higher_tier_gives_larger_bonus(self) -> None:
        """Sharing basil (HIGH) should bonus more than sharing milk (MEDIUM)."""
        high_lists = [
            [Ingredient(name="basil")],
            [Ingredient(name="basil")],
        ]
        med_lists = [
            [Ingredient(name="milk")],
            [Ingredient(name="milk")],
        ]
        high_bonus = ingredient_overlap_bonus(high_lists)
        med_bonus = ingredient_overlap_bonus(med_lists)
        assert high_bonus > med_bonus > 0.0

    def test_three_recipes_sharing_scales_bonus(self) -> None:
        """3 recipes sharing milk should bonus more than 2."""
        two_share = [
            [Ingredient(name="milk")],
            [Ingredient(name="milk")],
        ]
        three_share = [
            [Ingredient(name="milk")],
            [Ingredient(name="milk")],
            [Ingredient(name="milk")],
        ]
        assert ingredient_overlap_bonus(three_share) > ingredient_overlap_bonus(two_share)

    def test_custom_config_adjusts_bonus(self) -> None:
        lists = [
            [Ingredient(name="milk")],
            [Ingredient(name="milk")],
        ]
        default_bonus = ingredient_overlap_bonus(lists)
        boosted = ingredient_overlap_bonus(
            lists, SpoilageConfig(overlap_bonus_per_shared=0.10)
        )
        assert boosted > default_bonus

    def test_deduplicates_within_recipe(self) -> None:
        """Same ingredient listed twice in one recipe should count as one."""
        lists = [
            [Ingredient(name="milk"), Ingredient(name="milk")],
            [Ingredient(name="milk")],
        ]
        single = [
            [Ingredient(name="milk")],
            [Ingredient(name="milk")],
        ]
        assert ingredient_overlap_bonus(lists) == ingredient_overlap_bonus(single)


# ── plan_spoilage_penalty ────────────────────────────────────────────────


class TestPlanSpoilagePenalty:
    def test_no_orphaned_perishables(self) -> None:
        lists = [
            [Ingredient(name="milk"), Ingredient(name="butter")],
            [Ingredient(name="milk"), Ingredient(name="butter")],
        ]
        penalty = plan_spoilage_penalty(lists)
        assert penalty == 0.0

    def test_orphaned_high_tier_penalised(self) -> None:
        lists = [
            [Ingredient(name="basil"), Ingredient(name="rice")],
            [Ingredient(name="chicken"), Ingredient(name="rice")],
        ]
        penalty = plan_spoilage_penalty(lists)
        assert penalty > 0.0

    def test_only_stable_no_penalty(self) -> None:
        lists = [
            [Ingredient(name="pasta")],
            [Ingredient(name="rice")],
        ]
        assert plan_spoilage_penalty(lists) == 0.0


# ── estimate_package_waste ───────────────────────────────────────────────


class TestEstimatePackageWaste:
    def test_exact_package_fit_no_waste(self) -> None:
        """Using exactly 4 cups of milk = 1 quart, zero waste."""
        ingredients = [
            Ingredient(name="milk", quantity=2.0, unit="cup"),
            Ingredient(name="milk", quantity=2.0, unit="cup"),
        ]
        waste = estimate_package_waste(ingredients)
        assert waste == 0.0

    def test_partial_use_produces_waste(self) -> None:
        """Using 1 cup of milk from a 2-cup pint = 50% waste."""
        ingredients = [Ingredient(name="milk", quantity=1.0, unit="cup")]
        waste = estimate_package_waste(ingredients)
        assert waste > 0.0
        assert waste <= 1.0

    def test_larger_use_less_waste(self) -> None:
        """Using 3.5 cups of milk wastes less than using 1 cup."""
        small = [Ingredient(name="milk", quantity=1.0, unit="cup")]
        large = [
            Ingredient(name="milk", quantity=2.0, unit="cup"),
            Ingredient(name="milk", quantity=1.5, unit="cup"),
        ]
        assert estimate_package_waste(small) > estimate_package_waste(large)

    def test_unknown_ingredient_skipped(self) -> None:
        """Ingredients without package data don't contribute."""
        ingredients = [Ingredient(name="xanthan gum", quantity=1.0, unit="tsp")]
        assert estimate_package_waste(ingredients) == 0.0

    def test_mismatched_unit_skipped(self) -> None:
        """Milk measured in 'tbsp' doesn't match package sizes in 'cup'."""
        ingredients = [Ingredient(name="milk", quantity=2.0, unit="tbsp")]
        assert estimate_package_waste(ingredients) == 0.0

    def test_picks_smallest_sufficient_package(self) -> None:
        """3 cups of milk should use a quart (4 cups), not a half-gallon."""
        ingredients = [
            Ingredient(name="milk", quantity=1.5, unit="cup"),
            Ingredient(name="milk", quantity=1.5, unit="cup"),
        ]
        waste = estimate_package_waste(ingredients)
        # 3 cups from a 4-cup quart = 25% waste
        assert 0.20 <= waste <= 0.30


# ── Scoring magnitude ────────────────────────────────────────────────────


class TestScoringMagnitude:
    """Verify that spoilage scores stay small relative to typical macro deviation."""

    def test_overlap_bonus_is_small(self) -> None:
        """Even heavy overlap should produce a bonus well under 1.0."""
        lists = [
            [Ingredient(name="milk"), Ingredient(name="basil"), Ingredient(name="chicken")],
            [Ingredient(name="milk"), Ingredient(name="basil"), Ingredient(name="chicken")],
            [Ingredient(name="milk"), Ingredient(name="basil"), Ingredient(name="chicken")],
        ]
        bonus = ingredient_overlap_bonus(lists)
        # With default config, spoilage_weight=0.10 applied in optimizer,
        # so effective contribution = bonus * 0.10 — should be tiny
        assert bonus < 1.0

    def test_spoilage_weight_caps_contribution(self) -> None:
        """overlap_bonus * spoilage_weight should be << typical macro_deviation (~2-5)."""
        lists = [
            [Ingredient(name="milk"), Ingredient(name="basil"), Ingredient(name="spinach")],
            [Ingredient(name="milk"), Ingredient(name="basil"), Ingredient(name="spinach")],
        ]
        config = SpoilageConfig()
        bonus = ingredient_overlap_bonus(lists, config)
        effective = bonus * config.spoilage_weight
        # Typical macro_deviation is 2-5; this should be < 0.1
        assert effective < 0.1
