"""FastMCP server with tool definitions.

This module defines all MCP tools that Claude Desktop and other MCP clients
can call. Each tool delegates to the core library for actual logic.
"""

from __future__ import annotations

from fastmcp import FastMCP

from mealmcp.core.models import (
    MealComponent,
    MealType,
    OptimizationObjective,
    RebalanceStrategy,
    RecipeCategory,
)
from mealmcp.core.schemas import (
    ComplementSuggestionSchema,
    GroceryListSchema,
    MacroSummarySchema,
    MacroTargetSchema,
    MealCompositionSchema,
    MealComponentSchema,
    MealPlanSchema,
    MealPlanSummarySchema,
    MealSlotSchema,
    MemberSchema,
    OptimizedMealSchema,
    OptimizedPlanSchema,
    RebalancedPlanSchema,
    RecipeDetailSchema,
    RecipeSearchPageSchema,
)

mcp = FastMCP("MealMCP", description="Meal planning with macro optimization")


# ── Search Tools ──────────────────────────────────────────────────────────


@mcp.tool()
async def search_recipes_by_query(
    query: str,
    category: str | None = None,
    tags: list[str] | None = None,
    max_results: int = 5,
    cursor: str | None = None,
    min_confidence: float = 0.0,
) -> RecipeSearchPageSchema:
    """Search recipes by natural language query using hybrid ranking.

    Combines FTS5 keyword matching with semantic vector similarity using
    Reciprocal Rank Fusion. Keyword matches are boosted so exact terms
    always surface first, while semantic search catches related concepts.

    Returns slim results (no ingredients/instructions). Use
    get_recipe_detail(recipe_id) for full info.
    """
    from mealmcp.core.search import hybrid_search

    cat = RecipeCategory(category) if category else None
    offset = int(cursor) if cursor else 0

    # Generate embedding for semantic search
    embedding: list[float] | None = None
    try:
        from mealmcp.pipeline.embeddings import generate_embedding
        from mealmcp.core.models import Recipe

        # Create a minimal recipe-like object for embedding
        dummy = Recipe(id="", family_id="", name=query, source="manual")  # type: ignore[arg-type]
        embedding = generate_embedding(dummy)
    except ImportError:
        pass  # sentence-transformers not available — FTS-only

    result = hybrid_search(
        query=query,
        embedding=embedding,
        category=cat,
        tags=tags,
        max_results=max_results,
        min_confidence=min_confidence,
        offset=offset,
    )

    return RecipeSearchPageSchema(
        hits=[
            {  # type: ignore[misc]
                "id": h.id,
                "name": h.name,
                "category": h.category,
                "tags": h.tags,
                "prep_minutes": h.prep_minutes,
                "cook_minutes": h.cook_minutes,
                "macro_summary": MacroSummarySchema(
                    calories=h.macro_summary.calories,
                    protein_g=h.macro_summary.protein_g,
                    carbs_g=h.macro_summary.carbs_g,
                    fat_g=h.macro_summary.fat_g,
                ),
                "search_score": h.search_score,
                "match_type": h.match_type,
            }
            for h in result.hits
        ],
        next_cursor=result.next_cursor,
        total_count=result.total_count,
    )


@mcp.tool()
async def search_recipes_by_macros(
    target_calories: float | None = None,
    target_protein_g: float | None = None,
    target_carbs_g: float | None = None,
    target_fat_g: float | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    max_results: int = 5,
    cursor: str | None = None,
    tolerance_pct: float = 20.0,
) -> RecipeSearchPageSchema:
    """Find recipes closest to target macros.

    At least one target macro must be provided. Results are ranked by
    weighted Euclidean distance in normalized macro-space.

    Returns slim results — use get_recipe_detail(id) for full info.
    """
    from mealmcp.core.search import macro_distance_search

    cat = RecipeCategory(category) if category else None
    offset = int(cursor) if cursor else 0

    result = macro_distance_search(
        target_calories=target_calories,
        target_protein_g=target_protein_g,
        target_carbs_g=target_carbs_g,
        target_fat_g=target_fat_g,
        category=cat,
        tags=tags,
        max_results=max_results,
        tolerance_pct=tolerance_pct,
        offset=offset,
    )

    return RecipeSearchPageSchema(
        hits=[
            {  # type: ignore[misc]
                "id": h.id,
                "name": h.name,
                "category": h.category,
                "tags": h.tags,
                "prep_minutes": h.prep_minutes,
                "cook_minutes": h.cook_minutes,
                "macro_summary": MacroSummarySchema(
                    calories=h.macro_summary.calories,
                    protein_g=h.macro_summary.protein_g,
                    carbs_g=h.macro_summary.carbs_g,
                    fat_g=h.macro_summary.fat_g,
                ),
                "search_score": h.search_score,
                "match_type": h.match_type,
            }
            for h in result.hits
        ],
        next_cursor=result.next_cursor,
        total_count=result.total_count,
    )


# ── Recipe Detail ─────────────────────────────────────────────────────────


@mcp.tool()
async def get_recipe_detail(recipe_id: str) -> RecipeDetailSchema | None:
    """Get complete recipe information: ingredients, instructions,
    full nutrition breakdown, and tags."""
    from mealmcp.core.recipe_store import get_nutrition, get_recipe

    recipe = get_recipe(recipe_id)
    if recipe is None:
        return None

    nutrition = get_nutrition(recipe_id)

    return RecipeDetailSchema(
        id=recipe.id,
        family_id=recipe.family_id,
        name=recipe.name,
        source=recipe.source,
        ingredients=[
            {"name": i.name, "quantity": i.quantity, "unit": i.unit,  # type: ignore[misc]
             "raw_text": i.raw_text, "sub_recipe_id": i.sub_recipe_id}
            for i in recipe.ingredients
        ],
        instructions=recipe.instructions,
        servings=recipe.servings,
        prep_minutes=recipe.prep_minutes,
        cook_minutes=recipe.cook_minutes,
        tags=recipe.tags,
        category=recipe.category,
        image_url=recipe.image_url,
        nutrition=(
            {  # type: ignore[arg-type]
                "recipe_id": nutrition.recipe_id,
                "calories": nutrition.calories,
                "protein_g": nutrition.protein_g,
                "carbs_g": nutrition.carbs_g,
                "fat_g": nutrition.fat_g,
                "fiber_g": nutrition.fiber_g,
                "sodium_mg": nutrition.sodium_mg,
                "source": nutrition.source,
                "confidence": nutrition.confidence,
                "computed_at": nutrition.computed_at,
            }
            if nutrition
            else None
        ),
        created_at=recipe.created_at,
        updated_at=recipe.updated_at,
    )


# ── Meal Composition ─────────────────────────────────────────────────────


@mcp.tool()
async def compose_meal(
    components: list[dict[str, float | str]],
    member_id: str | None = None,
    target_name: str | None = None,
) -> MealCompositionSchema:
    """Compose a meal from multiple recipes and compute aggregate nutrition.

    If member_id is provided, compares against their active macro target.
    Designed for iterative refinement — search, compose, adjust, repeat.
    """
    from mealmcp.core.meal_composer import compose_meal as _compose

    meal_components = [
        MealComponent(
            recipe_id=str(c["recipe_id"]),
            servings=float(c.get("servings", 1.0)),
        )
        for c in components
    ]

    result = _compose(meal_components, member_id, target_name)

    return MealCompositionSchema(
        components=[
            {  # type: ignore[misc]
                "recipe_id": cn.recipe_id,
                "recipe_name": cn.recipe_name,
                "servings": cn.servings,
                "macros": MacroSummarySchema(
                    calories=cn.macros.calories,
                    protein_g=cn.macros.protein_g,
                    carbs_g=cn.macros.carbs_g,
                    fat_g=cn.macros.fat_g,
                ),
            }
            for cn in result.components
        ],
        totals=MacroSummarySchema(
            calories=result.totals.calories,
            protein_g=result.totals.protein_g,
            carbs_g=result.totals.carbs_g,
            fat_g=result.totals.fat_g,
        ),
        member_deltas={
            mid: MacroSummarySchema(
                calories=d.calories,
                protein_g=d.protein_g,
                carbs_g=d.carbs_g,
                fat_g=d.fat_g,
            )
            for mid, d in result.member_deltas.items()
        },
        suggestions=result.suggestions,
    )


@mcp.tool()
async def suggest_meal_complement(
    existing_recipe_ids: list[str],
    existing_servings: list[float],
    member_id: str,
    complement_category: str = "side",
    max_results: int = 5,
) -> list[ComplementSuggestionSchema]:
    """Suggest sides/additions that bring a partial meal closer to macro targets.

    "I have grilled chicken — what side gets me closest to my targets?"
    """
    from mealmcp.core.meal_composer import suggest_complements

    cat = RecipeCategory(complement_category)
    results = suggest_complements(
        existing_recipe_ids, existing_servings, member_id, cat, max_results
    )

    return [
        ComplementSuggestionSchema(
            recipe_id=s.recipe_id,
            recipe_name=s.recipe_name,
            category=s.category,
            suggested_servings=s.suggested_servings,
            projected_totals=MacroSummarySchema(
                calories=s.projected_totals.calories,
                protein_g=s.projected_totals.protein_g,
                carbs_g=s.projected_totals.carbs_g,
                fat_g=s.projected_totals.fat_g,
            ),
            projected_deviation=MacroSummarySchema(
                calories=s.projected_deviation.calories,
                protein_g=s.projected_deviation.protein_g,
                carbs_g=s.projected_deviation.carbs_g,
                fat_g=s.projected_deviation.fat_g,
            ),
        )
        for s in results
    ]


# ── Meal Plan CRUD ───────────────────────────────────────────────────────


@mcp.tool()
async def create_meal_plan(
    name: str,
    start_date: str,
    family_id: str,
    days: int = 7,
) -> MealPlanSchema:
    """Create an empty meal plan scaffold."""
    from datetime import date

    from mealmcp.core.planner import create_meal_plan as _create

    plan = _create(
        family_id=family_id,
        name=name,
        start_date=date.fromisoformat(start_date),
        days=days,
    )

    return MealPlanSchema(
        id=plan.id,
        family_id=plan.family_id,
        name=plan.name,
        start_date=plan.start_date,
        days=plan.days,
        created_at=plan.created_at,
    )


@mcp.tool()
async def add_to_meal_plan(
    plan_id: str,
    day_offset: int,
    meal_type: str,
    recipe_id: str,
    servings: float = 1.0,
    member_servings: dict[str, float] | None = None,
) -> list[MealSlotSchema]:
    """Add a recipe to a specific slot in the meal plan.

    Returns the updated day with all slots.
    """
    from mealmcp.core.planner import add_meal_slot, get_meal_slots

    mt = MealType(meal_type)
    add_meal_slot(plan_id, day_offset, mt, recipe_id, servings, member_servings)

    slots = get_meal_slots(plan_id, day_offset)
    return [
        MealSlotSchema(
            plan_id=s.plan_id,
            day_offset=s.day_offset,
            meal_type=s.meal_type,
            recipe_id=s.recipe_id,
            servings=s.servings,
            member_servings=s.member_servings,
        )
        for s in slots
    ]


@mcp.tool()
async def get_meal_plan_summary(
    plan_id: str,
    member_id: str | None = None,
    day_offset: int | None = None,
    detail_level: str = "daily",
) -> MealPlanSummarySchema:
    """Plan overview with configurable granularity.

    detail_level controls response size:
    - "weekly": just weekly averages per member vs. targets (~200 tokens)
    - "daily": per-day macro totals per member (~500 tokens)
    - "full": per-day, per-meal breakdown (~1500 tokens)
    """
    from mealmcp.core.models import DetailLevel

    from mealmcp.core.planner import get_meal_plan, get_meal_slots
    from mealmcp.core.recipe_store import get_nutrition_batch

    plan = get_meal_plan(plan_id)
    if plan is None:
        return MealPlanSummarySchema(
            plan_id=plan_id,
            plan_name="",
            start_date="2000-01-01",  # type: ignore[arg-type]
            days=0,
            detail_level=DetailLevel(detail_level),
        )

    slots = get_meal_slots(plan_id, day_offset)
    nutrition_map = get_nutrition_batch([s.recipe_id for s in slots])

    # Compute daily summaries
    from mealmcp.core.schemas import MealPlanDaySummarySchema

    daily_summaries: list[MealPlanDaySummarySchema] = []
    # Group by day
    days_data: dict[int, list[object]] = {}
    for s in slots:
        days_data.setdefault(s.day_offset, []).append(s)

    for day in sorted(days_data.keys()):
        day_slots = days_data[day]
        day_macros: dict[str, list[float]] = {}

        meals: dict[str, list[MealComponentSchema]] = {}
        for s in day_slots:
            if not isinstance(s, type(slots[0])):
                continue
            nutr = nutrition_map.get(s.recipe_id)
            meal_key = s.meal_type.value

            if detail_level == "full":
                meals.setdefault(meal_key, []).append(
                    MealComponentSchema(recipe_id=s.recipe_id, servings=s.servings)
                )

            if nutr is None:
                continue

            # Aggregate for each member in member_servings, or use default
            members_to_track = (
                [member_id] if member_id else list(s.member_servings.keys())
            )
            if not members_to_track:
                members_to_track = ["_default"]

            for mid in members_to_track:
                srv = s.member_servings.get(mid, s.servings) if mid != "_default" else s.servings
                if mid not in day_macros:
                    day_macros[mid] = [0.0, 0.0, 0.0, 0.0]
                day_macros[mid][0] += nutr.calories * srv
                day_macros[mid][1] += nutr.protein_g * srv
                day_macros[mid][2] += nutr.carbs_g * srv
                day_macros[mid][3] += nutr.fat_g * srv

        daily_summaries.append(
            MealPlanDaySummarySchema(
                day_offset=day,
                member_macros={
                    mid: MacroSummarySchema(
                        calories=v[0], protein_g=v[1], carbs_g=v[2], fat_g=v[3]
                    )
                    for mid, v in day_macros.items()
                },
                meals=meals if detail_level == "full" else {},
            )
        )

    # Weekly averages
    weekly_avgs: dict[str, MacroSummarySchema] = {}
    if daily_summaries:
        all_members: set[str] = set()
        for ds in daily_summaries:
            all_members.update(ds.member_macros.keys())

        for mid in all_members:
            member_days = [
                ds.member_macros[mid]
                for ds in daily_summaries
                if mid in ds.member_macros
            ]
            if member_days:
                n = len(member_days)
                weekly_avgs[mid] = MacroSummarySchema(
                    calories=sum(d.calories for d in member_days) / n,
                    protein_g=sum(d.protein_g for d in member_days) / n,
                    carbs_g=sum(d.carbs_g for d in member_days) / n,
                    fat_g=sum(d.fat_g for d in member_days) / n,
                )

    return MealPlanSummarySchema(
        plan_id=plan_id,
        plan_name=plan.name,
        start_date=plan.start_date,
        days=plan.days,
        detail_level=DetailLevel(detail_level),
        daily_summaries=daily_summaries if detail_level != "weekly" else [],
        weekly_averages=weekly_avgs,
    )


# ── Grocery List ──────────────────────────────────────────────────────────


@mcp.tool()
async def generate_grocery_list(
    plan_id: str,
    merge_similar: bool = True,
    exclude_pantry: bool = True,
) -> GroceryListSchema:
    """Generate a consolidated grocery list from a meal plan.

    Groups by category and sums quantities across all recipes and servings.
    """
    from mealmcp.core.grocery import generate_grocery_list as _generate

    result = _generate(plan_id, merge_similar, exclude_pantry)

    return GroceryListSchema(
        plan_id=result.plan_id,
        items=[
            {  # type: ignore[misc]
                "name": item.name,
                "quantity": item.quantity,
                "unit": item.unit,
                "category": item.category,
                "recipe_sources": item.recipe_sources,
            }
            for item in result.items
        ],
    )


# ── Tags & Categories ────────────────────────────────────────────────────


@mcp.tool()
async def list_tags() -> list[str]:
    """List all available recipe tags for filtering."""
    from mealmcp.core.recipe_store import list_all_tags

    return list_all_tags()


@mcp.tool()
async def list_categories() -> list[str]:
    """List all available recipe categories."""
    from mealmcp.core.recipe_store import list_all_categories

    return list_all_categories()


# ── Macro Targets ─────────────────────────────────────────────────────────


@mcp.tool()
async def get_macro_targets(
    member_id: str | None = None,
) -> list[MacroTargetSchema]:
    """List macro target profiles, optionally filtered by member."""
    from mealmcp.core.db import get_cursor

    if member_id:
        condition = " WHERE member_id = ?"
        params: list[str] = [member_id]
    else:
        condition = ""
        params = []

    with get_cursor() as cursor:
        cursor.execute(f"SELECT * FROM macro_targets{condition}", params)
        rows = cursor.fetchall()

    return [
        MacroTargetSchema(
            id=str(row["id"]),
            member_id=str(row["member_id"]),
            name=str(row["name"]),
            calories=float(str(row["calories"])),
            protein_g=float(str(row["protein_g"])),
            carbs_g=float(str(row["carbs_g"])),
            fat_g=float(str(row["fat_g"])),
            is_active=bool(row["is_active"]),
        )
        for row in rows
    ]


# ── Family & Member Management ───────────────────────────────────────────


@mcp.tool()
async def list_family_members(
    family_id: str | None = None,
) -> list[MemberSchema]:
    """List all members of a family with their active macro targets."""
    from mealmcp.core.db import get_cursor

    if family_id:
        condition = " WHERE family_id = ?"
        params: list[str] = [family_id]
    else:
        condition = ""
        params = []

    with get_cursor() as cursor:
        cursor.execute(f"SELECT * FROM members{condition}", params)
        rows = cursor.fetchall()

    return [
        MemberSchema(
            id=str(row["id"]),
            family_id=str(row["family_id"]),
            name=str(row["name"]),
            role=row["role"],
            is_default=bool(row["is_default"]),
        )
        for row in rows
    ]


@mcp.tool()
async def set_macro_target(
    member_id: str,
    name: str,
    calories: float,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    set_active: bool = True,
) -> MacroTargetSchema:
    """Create or update a macro target for a member."""
    import uuid

    from mealmcp.core.db import get_cursor

    target_id = str(uuid.uuid4())

    with get_cursor() as cursor:
        if set_active:
            # Deactivate other targets for this member
            cursor.execute(
                "UPDATE macro_targets SET is_active = 0 WHERE member_id = ?",
                (member_id,),
            )

        cursor.execute(
            """
            INSERT INTO macro_targets (id, member_id, name, calories, protein_g,
                                       carbs_g, fat_g, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (target_id, member_id, name, calories, protein_g, carbs_g, fat_g, int(set_active)),
        )

    return MacroTargetSchema(
        id=target_id,
        member_id=member_id,
        name=name,
        calories=calories,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        is_active=set_active,
    )


# ── Optimization Tools ───────────────────────────────────────────────────


@mcp.tool()
async def optimize_meal(
    member_ids: list[str],
    meal_type: str,
    candidate_recipe_ids: list[str] | None = None,
    required_recipe_ids: list[str] | None = None,
    excluded_recipe_ids: list[str] | None = None,
    max_components: int = 4,
    allow_fractional_servings: bool = True,
    num_alternatives: int = 3,
) -> list[OptimizedMealSchema]:
    """Find the optimal combination of recipes and servings for a single meal.

    Returns num_alternatives solutions ranked by objective score.
    """
    from mealmcp.core.optimizer import optimize_meal as _optimize

    mt = MealType(meal_type)
    results = _optimize(
        member_ids=member_ids,
        meal_type=mt,
        candidate_recipe_ids=candidate_recipe_ids,
        required_recipe_ids=required_recipe_ids,
        excluded_recipe_ids=excluded_recipe_ids,
        max_components=max_components,
        allow_fractional_servings=allow_fractional_servings,
        num_alternatives=num_alternatives,
    )

    return [
        OptimizedMealSchema(
            recipes=[
                MealComponentSchema(recipe_id=r.recipe_id, servings=r.servings)
                for r in om.recipes
            ],
            member_servings=om.member_servings,
            member_macros={
                mid: MacroSummarySchema(
                    calories=m.calories, protein_g=m.protein_g,
                    carbs_g=m.carbs_g, fat_g=m.fat_g,
                )
                for mid, m in om.member_macros.items()
            },
            member_deviation={
                mid: MacroSummarySchema(
                    calories=m.calories, protein_g=m.protein_g,
                    carbs_g=m.carbs_g, fat_g=m.fat_g,
                )
                for mid, m in om.member_deviation.items()
            },
            objective_score=om.objective_score,
            solve_time_ms=om.solve_time_ms,
        )
        for om in results
    ]


@mcp.tool()
async def optimize_plan(
    plan_id: str,
    member_ids: list[str],
    meal_types: list[str] | None = None,
    max_components_per_meal: int = 3,
) -> OptimizedPlanSchema:
    """Fill all empty slots in a meal plan optimally across the full week."""
    from mealmcp.core.optimizer import optimize_plan as _optimize

    mt = [MealType(m) for m in meal_types] if meal_types else None
    result = _optimize(
        plan_id=plan_id,
        member_ids=member_ids,
        meal_types=mt,
        max_components_per_meal=max_components_per_meal,
    )

    return OptimizedPlanSchema(
        plan_id=result.plan_id,
        slots=[
            MealSlotSchema(
                plan_id=s.plan_id, day_offset=s.day_offset,
                meal_type=s.meal_type, recipe_id=s.recipe_id,
                servings=s.servings, member_servings=s.member_servings,
            )
            for s in result.slots
        ],
        total_deviation=result.total_deviation,
        recipe_usage_counts=result.recipe_usage_counts,
        solve_time_ms=result.solve_time_ms,
    )


@mcp.tool()
async def rebalance_plan(
    plan_id: str,
    member_id: str,
    strategy: str = "adjust_servings",
) -> RebalancedPlanSchema:
    """Fine-tune an existing plan for one member.

    Strategies:
    - "adjust_servings": keep all recipes, solve for optimal serving sizes
    - "swap_sides": keep mains fixed, try swapping sides
    """
    from mealmcp.core.optimizer import rebalance_plan as _rebalance

    strat = RebalanceStrategy(strategy)
    result = _rebalance(plan_id, member_id, strat)

    return RebalancedPlanSchema(
        plan_id=result.plan_id,
        member_id=result.member_id,
        strategy=result.strategy,
        before_macros={
            d: MacroSummarySchema(
                calories=m.calories, protein_g=m.protein_g,
                carbs_g=m.carbs_g, fat_g=m.fat_g,
            )
            for d, m in result.before_macros.items()
        },
        after_macros={
            d: MacroSummarySchema(
                calories=m.calories, protein_g=m.protein_g,
                carbs_g=m.carbs_g, fat_g=m.fat_g,
            )
            for d, m in result.after_macros.items()
        },
        adjusted_slots=[
            MealSlotSchema(
                plan_id=s.plan_id, day_offset=s.day_offset,
                meal_type=s.meal_type, recipe_id=s.recipe_id,
                servings=s.servings, member_servings=s.member_servings,
            )
            for s in result.adjusted_slots
        ],
    )
