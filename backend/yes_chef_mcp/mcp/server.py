"""FastMCP backend with tool definitions.

This module defines all MCP tools that Claude Desktop and other MCP clients
can call. Each tool delegates to the core library for actual logic.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastmcp import FastMCP
from fastmcp.apps import AppConfig, ResourceCSP

from yes_chef_mcp.core.db import get_db
from yes_chef_mcp.core.grocery import generate_grocery_list as _generate_grocery
from yes_chef_mcp.core.meal_composer import compose_meal as _compose, suggest_complements
from yes_chef_mcp.core.models import (
    DetailLevel,
    MealComponent,
    MealType,
    OptimizationObjective,
    RebalanceStrategy,
    RecipeCategory,
)
from yes_chef_mcp.core.optimizer import (
    optimize_meal as _optimize_meal,
    optimize_plan as _optimize_plan,
    rebalance_plan as _rebalance_plan,
)
from yes_chef_mcp.core.planner import (
    add_meal_slot,
    create_meal_plan as _create_plan,
    get_meal_plan,
    get_meal_slots,
    list_meal_plans,
    remove_meal_slot,
)
from yes_chef_mcp.core.recipe_store import (
    get_nutrition,
    get_nutrition_batch,
    get_recipe,
    list_all_categories,
    list_all_tags,
)
from yes_chef_mcp.core.schemas import (
    ComplementSuggestionSchema,
    GroceryListSchema,
    MacroSummarySchema,
    MacroTargetSchema,
    MealComponentSchema,
    MealCompositionSchema,
    MealPlanDaySummarySchema,
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
from yes_chef_mcp.core.search import hybrid_search, macro_distance_search

mcp = FastMCP("yes_chef_mcp", instructions="Meal planning with macro optimization")


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
    cat = RecipeCategory(category) if category else None
    offset = int(cursor) if cursor else 0

    embedding: list[float] | None = None
    try:
        from yes_chef_mcp.pipeline.embeddings import generate_embedding
        from yes_chef_mcp.core.models import Recipe

        dummy = Recipe(id="", family_id="", name=query, source="manual")  # type: ignore[arg-type]
        embedding = generate_embedding(dummy)
    except ImportError:
        pass  # sentence-transformers not available — FTS-only

    result = await hybrid_search(
        query=query,
        embedding=embedding,
        category=cat,
        tags=tags,
        max_results=max_results,
        min_confidence=min_confidence,
        offset=offset,
    )

    return RecipeSearchPageSchema.model_validate(result)


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
    cat = RecipeCategory(category) if category else None
    offset = int(cursor) if cursor else 0

    result = await macro_distance_search(
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

    return RecipeSearchPageSchema.model_validate(result)


# ── Recipe Detail ─────────────────────────────────────────────────────────


@mcp.tool()
async def get_recipe_detail(recipe_id: str) -> RecipeDetailSchema | None:
    """Get complete recipe information: ingredients, instructions,
    full nutrition breakdown, and tags."""
    recipe = await get_recipe(recipe_id)
    if recipe is None:
        return None

    nutrition = await get_nutrition(recipe_id)

    return RecipeDetailSchema.model_validate(
        {
            "id": recipe.id,
            "family_id": recipe.family_id,
            "name": recipe.name,
            "source": recipe.source,
            "ingredients": recipe.ingredients,
            "instructions": recipe.instructions,
            "servings": recipe.servings,
            "prep_minutes": recipe.prep_minutes,
            "cook_minutes": recipe.cook_minutes,
            "tags": recipe.tags,
            "category": recipe.category,
            "image_url": recipe.image_url,
            "nutrition": nutrition,
            "created_at": recipe.created_at,
            "updated_at": recipe.updated_at,
        }
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
    meal_components = [
        MealComponent(
            recipe_id=str(c["recipe_id"]),
            servings=float(c.get("servings", 1.0)),
        )
        for c in components
    ]

    result = await _compose(meal_components, member_id, target_name)

    return MealCompositionSchema.model_validate(result)


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
    cat = RecipeCategory(complement_category)
    results = await suggest_complements(
        existing_recipe_ids, existing_servings, member_id, cat, max_results
    )

    return [ComplementSuggestionSchema.model_validate(s) for s in results]


# ── Meal Plan CRUD ───────────────────────────────────────────────────────


@mcp.tool()
async def create_meal_plan(
    name: str,
    start_date: str,
    family_id: str,
    days: int = 7,
) -> MealPlanSchema:
    """Create an empty meal plan scaffold."""
    plan = await _create_plan(
        family_id=family_id,
        name=name,
        start_date=date.fromisoformat(start_date),
        days=days,
    )

    return MealPlanSchema.model_validate(plan)


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
    mt = MealType(meal_type)
    await add_meal_slot(plan_id, day_offset, mt, recipe_id, servings, member_servings)

    slots = await get_meal_slots(plan_id, day_offset)
    return [MealSlotSchema.model_validate(s) for s in slots]


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
    plan = await get_meal_plan(plan_id)
    if plan is None:
        return MealPlanSummarySchema(
            plan_id=plan_id,
            plan_name="",
            start_date="2000-01-01",  # type: ignore[arg-type]
            days=0,
            detail_level=DetailLevel(detail_level),
        )

    slots = await get_meal_slots(plan_id, day_offset)
    nutrition_map = await get_nutrition_batch([s.recipe_id for s in slots])

    daily_summaries: list[MealPlanDaySummarySchema] = []
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
    result = await _generate_grocery(plan_id, merge_similar, exclude_pantry)

    return GroceryListSchema.model_validate(result)


# ── Tags & Categories ────────────────────────────────────────────────────


@mcp.tool()
async def list_tags() -> list[str]:
    """List all available recipe tags for filtering."""
    return await list_all_tags()


@mcp.tool()
async def list_categories() -> list[str]:
    """List all available recipe categories."""
    return await list_all_categories()


# ── Macro Targets ─────────────────────────────────────────────────────────


@mcp.tool()
async def get_macro_targets(
    member_id: str | None = None,
) -> list[MacroTargetSchema]:
    """List macro target profiles, optionally filtered by member."""
    if member_id:
        condition = " WHERE member_id = ?"
        params: list[str] = [member_id]
    else:
        condition = ""
        params = []

    async with get_db() as db:
        cursor = await db.execute(f"SELECT * FROM macro_targets{condition}", params)
        rows = await cursor.fetchall()

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
    if family_id:
        condition = " WHERE family_id = ?"
        params: list[str] = [family_id]
    else:
        condition = ""
        params = []

    async with get_db() as db:
        cursor = await db.execute(f"SELECT * FROM members{condition}", params)
        rows = await cursor.fetchall()

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
    target_id = str(uuid.uuid4())

    async with get_db() as db:
        if set_active:
            await db.execute(
                "UPDATE macro_targets SET is_active = 0 WHERE member_id = ?",
                (member_id,),
            )

        await db.execute(
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
    mt = MealType(meal_type)
    results = await _optimize_meal(
        member_ids=member_ids,
        meal_type=mt,
        candidate_recipe_ids=candidate_recipe_ids,
        required_recipe_ids=required_recipe_ids,
        excluded_recipe_ids=excluded_recipe_ids,
        max_components=max_components,
        allow_fractional_servings=allow_fractional_servings,
        num_alternatives=num_alternatives,
    )

    return [OptimizedMealSchema.model_validate(om) for om in results]


@mcp.tool()
async def optimize_plan(
    plan_id: str,
    member_ids: list[str],
    meal_types: list[str] | None = None,
    max_components_per_meal: int = 3,
) -> OptimizedPlanSchema:
    """Fill all empty slots in a meal plan optimally across the full week."""
    mt = [MealType(m) for m in meal_types] if meal_types else None
    result = await _optimize_plan(
        plan_id=plan_id,
        member_ids=member_ids,
        meal_types=mt,
        max_components_per_meal=max_components_per_meal,
    )

    return OptimizedPlanSchema.model_validate(result)


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
    strat = RebalanceStrategy(strategy)
    result = await _rebalance_plan(plan_id, member_id, strat)

    return RebalancedPlanSchema.model_validate(result)


# ── View Tools (MCP Apps Extension) ─────────────────────────────────────

# Each view tool returns JSON data that the linked ui:// resource renders.
# Hosts that support the MCP Apps extension display the HTML in a sandboxed
# iframe; the ext-apps SDK wires tool results into the React app.

_VIEW_CSP = ResourceCSP(
    resource_domains=["https://unpkg.com", "https://fonts.googleapis.com", "https://fonts.gstatic.com"],
)


@mcp.tool(
    app=AppConfig(resource_uri="ui://yes_chef_mcp/macro-setter.html"),
)
async def show_macro_target_setter(
    member_id: str | None = None,
) -> str:
    """Show an interactive macro target editor with sliders and pie chart.

    The user can adjust protein, carbs, and fat targets and see real-time
    calorie impact. When the user clicks Save, the app calls
    save_macro_targets with the new values.
    """
    import json

    targets = await get_macro_targets(member_id)
    active = next((t for t in targets if t.is_active), None)

    data: dict[str, object] = {}
    if active:
        data["current_targets"] = {
            "protein_g": active.protein_g,
            "carbs_g": active.carbs_g,
            "fat_g": active.fat_g,
            "calories": active.calories,
            "name": active.name,
        }

    return json.dumps(data)


@mcp.tool(
    app=AppConfig(
        resource_uri="ui://yes_chef_mcp/recipe-selector.html",
        visibility=["model"],
    ),
)
async def show_recipe_selector(
    query: str = "",
    category: str | None = None,
    tags: list[str] | None = None,
    max_results: int = 20,
) -> str:
    """Show a visual recipe browser with cards, category filters, and macro badges.

    Displays search results in a responsive grid. The user selects a recipe
    and the app calls select_recipe with the chosen recipe_id.
    """
    import json

    cat = RecipeCategory(category) if category else None
    embedding: list[float] | None = None
    try:
        from yes_chef_mcp.pipeline.embeddings import generate_embedding
        from yes_chef_mcp.core.models import Recipe

        dummy = Recipe(id="", family_id="", name=query, source="manual")  # type: ignore[arg-type]
        embedding = generate_embedding(dummy)
    except ImportError:
        pass

    result = await hybrid_search(
        query=query,
        embedding=embedding,
        category=cat,
        tags=tags,
        max_results=max_results,
    )

    recipes = [
        {
            "id": hit.id,
            "name": hit.name,
            "category": hit.category,
            "tags": hit.tags,
            "prep_minutes": hit.prep_minutes,
            "cook_minutes": hit.cook_minutes,
            "macro_summary": {
                "calories": hit.macro_summary.calories,
                "protein_g": hit.macro_summary.protein_g,
                "carbs_g": hit.macro_summary.carbs_g,
                "fat_g": hit.macro_summary.fat_g,
            },
        }
        for hit in result.hits
    ]

    return json.dumps({"recipes": recipes})


@mcp.tool(
    app=AppConfig(resource_uri="ui://yes_chef_mcp/weekly-calendar.html"),
)
async def show_weekly_calendar(
    plan_id: str,
    member_id: str | None = None,
) -> str:
    """Show a 7-day meal plan calendar with macro variance indicators.

    Displays all meals per day with color-coded progress bars showing
    proximity to daily macro targets. Includes action buttons for
    optimize, rebalance, and refresh.
    """
    import json

    summary = await get_meal_plan_summary(plan_id, member_id, detail_level="full")

    targets: dict[str, object] | None = None
    if member_id:
        target_list = await get_macro_targets(member_id)
        active = next((t for t in target_list if t.is_active), None)
        if active:
            targets = {
                "calories": active.calories,
                "protein_g": active.protein_g,
                "carbs_g": active.carbs_g,
                "fat_g": active.fat_g,
            }

    data: dict[str, object] = {"plan_summary": summary.model_dump()}
    if targets:
        data["targets"] = targets

    return json.dumps(data, default=str)


@mcp.tool(
    app=AppConfig(resource_uri="ui://yes_chef_mcp/grocery-list.html"),
)
async def show_grocery_checklist(
    plan_id: str,
    merge_similar: bool = True,
    exclude_pantry: bool = True,
) -> str:
    """Show an interactive grocery checklist grouped by ingredient category.

    Users can check off items they already have in their pantry. When they
    click Confirm, the app calls confirm_grocery_list with only the
    unchecked items they need to buy.
    """
    import json

    result = await _generate_grocery(plan_id, merge_similar, exclude_pantry)
    schema = GroceryListSchema.model_validate(result)

    return json.dumps({"grocery_list": schema.model_dump()}, default=str)


# ── UI Resources (MCP Apps) ─────────────────────────────────────────────

# Each resource serves the built HTML from the Vite dist/ directory.
# The HTML loads bundled JS/CSS that renders the React app.


@mcp.resource(
    "ui://yes_chef_mcp/macro-setter.html",
    app=AppConfig(csp=_VIEW_CSP),
)
def macro_setter_resource() -> str:
    """Interactive macro target editor UI."""
    from yes_chef_mcp.views import DIST_DIR

    return (DIST_DIR / "macro-setter.html").read_text()


@mcp.resource(
    "ui://yes_chef_mcp/recipe-selector.html",
    app=AppConfig(csp=_VIEW_CSP),
)
def recipe_selector_resource() -> str:
    """Recipe browser with card grid UI."""
    from yes_chef_mcp.views import DIST_DIR

    return (DIST_DIR / "recipe-selector.html").read_text()


@mcp.resource(
    "ui://yes_chef_mcp/weekly-calendar.html",
    app=AppConfig(csp=_VIEW_CSP),
)
def weekly_calendar_resource() -> str:
    """Weekly meal plan calendar UI."""
    from yes_chef_mcp.views import DIST_DIR

    return (DIST_DIR / "weekly-calendar.html").read_text()


@mcp.resource(
    "ui://yes_chef_mcp/grocery-list.html",
    app=AppConfig(csp=_VIEW_CSP),
)
def grocery_list_resource() -> str:
    """Grocery checklist UI."""
    from yes_chef_mcp.views import DIST_DIR

    return (DIST_DIR / "grocery-list.html").read_text()
