"""Tests for hybrid search."""

from __future__ import annotations

from mealmcp.core.models import Recipe, RecipeCategory
from mealmcp.core.search import hybrid_search, macro_distance_search


def test_fts_search_by_name(sample_recipes: list[Recipe]) -> None:
    results = hybrid_search(query="chicken")
    assert results.total_count >= 1
    assert any(h.id == "recipe-chicken" for h in results.hits)


def test_fts_search_by_ingredient(sample_recipes: list[Recipe]) -> None:
    results = hybrid_search(query="quinoa")
    assert results.total_count >= 1
    assert any(h.id == "recipe-quinoa" for h in results.hits)


def test_search_with_category_filter(sample_recipes: list[Recipe]) -> None:
    results = hybrid_search(query="chicken", category=RecipeCategory.SIDE)
    # Chicken is a main, not a side
    assert not any(h.id == "recipe-chicken" for h in results.hits)


def test_macro_distance_search(sample_recipes: list[Recipe]) -> None:
    results = macro_distance_search(
        target_calories=300.0,
        target_protein_g=40.0,
        max_results=5,
        tolerance_pct=50.0,
    )
    assert results.total_count >= 1
    # Chicken (280 cal, 45g protein) should be closest
    if results.hits:
        assert results.hits[0].id == "recipe-chicken"


def test_macro_search_with_category(sample_recipes: list[Recipe]) -> None:
    results = macro_distance_search(
        target_calories=200.0,
        category=RecipeCategory.SIDE,
        tolerance_pct=50.0,
    )
    # Only quinoa is a side
    assert all(h.category == RecipeCategory.SIDE for h in results.hits)
