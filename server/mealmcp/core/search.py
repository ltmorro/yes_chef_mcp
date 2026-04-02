"""Hybrid search combining FTS5 keyword matching with sqlite-vec vector similarity.

Uses Reciprocal Rank Fusion (RRF) to merge ranked lists from both sources.
"""

from __future__ import annotations

import json
import math
import struct

from mealmcp.core.db import get_db
from mealmcp.core.models import (
    MacroSummary,
    MatchType,
    RecipeCategory,
    RecipeSearchHit,
    RecipeSearchPage,
)
from mealmcp.core.recipe_store import get_nutrition_batch


def _rrf_score(rank: int, k: int = 60) -> float:
    """Reciprocal Rank Fusion score: 1 / (k + rank)."""
    return 1.0 / (k + rank)


async def _fts_search(query: str, limit: int) -> list[tuple[str, int]]:
    """Full-text search returning (recipe_id, rank) pairs."""
    async with get_db() as db:
        async with db.execute(
            """
            SELECT recipe_id, rank
            FROM recipes_fts
            WHERE recipes_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [(str(row["recipe_id"]), int(str(row["rank"]))) for row in rows]


async def _vector_search(
    embedding: list[float],
    limit: int,
) -> list[tuple[str, float]]:
    """Vector similarity search returning (recipe_id, distance) pairs."""
    vec_blob = struct.pack(f"{len(embedding)}f", *embedding)
    async with get_db() as db:
        async with db.execute(
            """
            SELECT recipe_id, distance
            FROM vec_recipes
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
            """,
            (vec_blob, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [(str(row["recipe_id"]), float(str(row["distance"]))) for row in rows]


async def _fetch_recipe_metadata(
    recipe_ids: list[str],
) -> dict[str, dict[str, str | int | None]]:
    """Fetch basic recipe metadata for search results."""
    if not recipe_ids:
        return {}
    placeholders = ",".join("?" for _ in recipe_ids)
    async with get_db() as db:
        async with db.execute(
            f"SELECT id, name, category, tags, prep_minutes, cook_minutes "
            f"FROM recipes WHERE id IN ({placeholders})",
            recipe_ids,
        ) as cursor:
            rows = await cursor.fetchall()
    return {str(row["id"]): dict(row) for row in rows}


async def hybrid_search(
    query: str,
    embedding: list[float] | None = None,
    category: RecipeCategory | None = None,
    tags: list[str] | None = None,
    max_results: int = 5,
    min_confidence: float = 0.0,
    offset: int = 0,
) -> RecipeSearchPage:
    """Hybrid search combining FTS5 keyword matching with vector similarity.

    Strategy:
    1. FTS5 keyword match on recipe name + ingredient names
    2. Vector similarity via sqlite-vec (if embedding provided)
    3. Reciprocal Rank Fusion merges both ranked lists

    Keyword matches are boosted so exact matches always rank first.
    """
    fetch_limit = max_results * 4  # Over-fetch for filtering

    # FTS5 keyword search
    fts_results = await _fts_search(query, fetch_limit)
    fts_ids = {rid for rid, _ in fts_results}

    # Vector similarity search (if embedding provided)
    vec_results: list[tuple[str, float]] = []
    vec_ids: set[str] = set()
    if embedding:
        vec_results = await _vector_search(embedding, fetch_limit)
        vec_ids = {rid for rid, _ in vec_results}

    # Reciprocal Rank Fusion
    scores: dict[str, float] = {}
    match_types: dict[str, MatchType] = {}

    # FTS results get a 2x boost for exact keyword relevance
    for rank, (rid, _) in enumerate(fts_results):
        scores[rid] = scores.get(rid, 0.0) + 2.0 * _rrf_score(rank)
        match_types[rid] = MatchType.KEYWORD

    for rank, (rid, _) in enumerate(vec_results):
        scores[rid] = scores.get(rid, 0.0) + _rrf_score(rank)
        if rid in fts_ids:
            match_types[rid] = MatchType.BOTH
        elif rid not in match_types:
            match_types[rid] = MatchType.SEMANTIC

    # Sort by fused score
    all_ids = sorted(scores, key=lambda rid: scores[rid], reverse=True)

    # Fetch metadata and nutrition for candidates
    metadata = await _fetch_recipe_metadata(all_ids)
    nutrition_map = await get_nutrition_batch(all_ids)

    # Filter and build results
    hits: list[RecipeSearchHit] = []
    for rid in all_ids:
        meta = metadata.get(rid)
        if meta is None:
            continue

        # Category filter
        if category and meta.get("category") != category.value:
            continue

        # Tag filter
        if tags:
            recipe_tags: list[str] = json.loads(str(meta.get("tags", "[]")))
            if not set(tags).intersection(recipe_tags):
                continue

        # Confidence filter
        nutr = nutrition_map.get(rid)
        if min_confidence > 0.0 and (nutr is None or nutr.confidence < min_confidence):
            continue

        macro_summary = MacroSummary(
            calories=nutr.calories if nutr else 0.0,
            protein_g=nutr.protein_g if nutr else 0.0,
            carbs_g=nutr.carbs_g if nutr else 0.0,
            fat_g=nutr.fat_g if nutr else 0.0,
        )

        recipe_tags_parsed: list[str] = json.loads(str(meta.get("tags", "[]")))
        cat_val = meta.get("category")
        recipe_category = RecipeCategory(str(cat_val)) if cat_val else None

        hits.append(
            RecipeSearchHit(
                id=rid,
                name=str(meta["name"]),
                category=recipe_category,
                tags=recipe_tags_parsed,
                prep_minutes=(
                    int(str(meta["prep_minutes"])) if meta.get("prep_minutes") is not None
                    else None
                ),
                cook_minutes=(
                    int(str(meta["cook_minutes"])) if meta.get("cook_minutes") is not None
                    else None
                ),
                macro_summary=macro_summary,
                search_score=scores[rid],
                match_type=match_types.get(rid, MatchType.KEYWORD),
            )
        )

    total = len(hits)
    page = hits[offset : offset + max_results]
    next_cursor = str(offset + max_results) if offset + max_results < total else None

    return RecipeSearchPage(
        hits=page,
        next_cursor=next_cursor,
        total_count=total,
    )


async def macro_distance_search(
    target_calories: float | None = None,
    target_protein_g: float | None = None,
    target_carbs_g: float | None = None,
    target_fat_g: float | None = None,
    category: RecipeCategory | None = None,
    tags: list[str] | None = None,
    max_results: int = 5,
    tolerance_pct: float = 20.0,
    offset: int = 0,
) -> RecipeSearchPage:
    """Find recipes closest to target macros using weighted Euclidean distance."""
    # Build query conditions
    conditions: list[str] = []
    params: list[str | float] = []

    if category:
        conditions.append("r.category = ?")
        params.append(category.value)

    if tags:
        placeholders = ",".join("?" for _ in tags)
        conditions.append(
            f"EXISTS (SELECT 1 FROM json_each(r.tags) AS jt WHERE jt.value IN ({placeholders}))"
        )
        params.extend(tags)

    where = f" AND {' AND '.join(conditions)}" if conditions else ""

    async with get_db() as db:
        async with db.execute(
            f"""
            SELECT r.id, r.name, r.category, r.tags, r.prep_minutes, r.cook_minutes,
                   n.calories, n.protein_g, n.carbs_g, n.fat_g
            FROM recipes r
            JOIN nutrition n ON r.id = n.recipe_id
            WHERE 1=1{where}
            """,
            params,
        ) as cursor:
            rows = await cursor.fetchall()

    # Compute distances
    scored: list[tuple[dict[str, str | int | float | None], float]] = []
    for row in rows:
        row_dict = dict(row)

        dist_sq = 0.0
        count = 0
        if target_calories is not None:
            diff = (float(str(row_dict["calories"])) - target_calories) / max(target_calories, 1)
            dist_sq += diff * diff
            count += 1
        if target_protein_g is not None:
            diff = (
                float(str(row_dict["protein_g"])) - target_protein_g
            ) / max(target_protein_g, 1)
            dist_sq += diff * diff * 1.5  # Protein premium
            count += 1
        if target_carbs_g is not None:
            diff = (float(str(row_dict["carbs_g"])) - target_carbs_g) / max(target_carbs_g, 1)
            dist_sq += diff * diff * 0.8
            count += 1
        if target_fat_g is not None:
            diff = (float(str(row_dict["fat_g"])) - target_fat_g) / max(target_fat_g, 1)
            dist_sq += diff * diff * 0.8
            count += 1

        if count == 0:
            continue

        distance = math.sqrt(dist_sq / count)

        # Tolerance filter
        if distance > tolerance_pct / 100.0:
            continue

        scored.append((row_dict, distance))

    scored.sort(key=lambda x: x[1])
    total = len(scored)
    page = scored[offset : offset + max_results]

    hits: list[RecipeSearchHit] = []
    for row_dict, distance in page:
        recipe_tags_parsed: list[str] = json.loads(str(row_dict.get("tags", "[]")))
        cat_val = row_dict.get("category")
        recipe_category = RecipeCategory(str(cat_val)) if cat_val else None

        hits.append(
            RecipeSearchHit(
                id=str(row_dict["id"]),
                name=str(row_dict["name"]),
                category=recipe_category,
                tags=recipe_tags_parsed,
                prep_minutes=(
                    int(str(row_dict["prep_minutes"]))
                    if row_dict.get("prep_minutes") is not None
                    else None
                ),
                cook_minutes=(
                    int(str(row_dict["cook_minutes"]))
                    if row_dict.get("cook_minutes") is not None
                    else None
                ),
                macro_summary=MacroSummary(
                    calories=float(str(row_dict["calories"])),
                    protein_g=float(str(row_dict["protein_g"])),
                    carbs_g=float(str(row_dict["carbs_g"])),
                    fat_g=float(str(row_dict["fat_g"])),
                ),
                search_score=1.0 / (1.0 + distance),  # Invert for ranking
                match_type=MatchType.KEYWORD,
            )
        )

    next_cursor = str(offset + max_results) if offset + max_results < total else None

    return RecipeSearchPage(
        hits=hits,
        next_cursor=next_cursor,
        total_count=total,
    )
