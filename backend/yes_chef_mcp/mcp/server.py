"""FastMCP backend with tool definitions.

This module defines all MCP tools that Claude Desktop and other MCP clients
can call. Each tool delegates to the core library for actual logic.
"""

from __future__ import annotations

import logging
from datetime import date

from fastmcp import FastMCP
from fastmcp.apps import AppConfig, ResourceCSP
from fastmcp.exceptions import ToolError
from fastmcp.tools import ToolResult
from mcp.types import ToolAnnotations

from yes_chef_mcp.core.grocery import generate_grocery_list as _generate_grocery
from yes_chef_mcp.core.meal_composer import compose_meal as _compose
from yes_chef_mcp.core.meal_composer import suggest_complements
from yes_chef_mcp.core.members import (
    create_macro_target,
    list_macro_targets,
    list_members,
)
from yes_chef_mcp.core.models import (
    DetailLevel,
    MealComponent,
    MealSlot,
    MealType,
    RebalanceStrategy,
    RecipeCategory,
)
from yes_chef_mcp.core.optimizer import (
    optimize_meal as _optimize_meal,
)
from yes_chef_mcp.core.optimizer import (
    optimize_plan as _optimize_plan,
)
from yes_chef_mcp.core.optimizer import (
    rebalance_plan as _rebalance_plan,
)
from yes_chef_mcp.core.planner import (
    add_meal_slot,
    get_meal_plan,
    get_meal_slots,
)
from yes_chef_mcp.core.planner import (
    create_meal_plan as _create_plan,
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
    GroceryListDataSchema,
    GroceryListSchema,
    MacroSetterDataSchema,
    MacroSetterTargetsSchema,
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
    RecipeSearchHitSchema,
    RecipeSearchPageSchema,
    RecipeSelectorDataSchema,
    WeeklyCalendarDataSchema,
)
from yes_chef_mcp.core.search import hybrid_search, macro_distance_search, search_by_ids

logger = logging.getLogger(__name__)

mcp = FastMCP("yes_chef_mcp", instructions="Meal planning with macro optimization")

# ── Tool annotations ─────────────────────────────────────────────────────
# Everything runs against the local SQLite database, so no tool is open-world.

_READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)

# create_meal_plan / set_macro_target insert a fresh row (new UUID) per call.
_CREATE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
)


# ── Search Tools ──────────────────────────────────────────────────────────


@mcp.tool(title="Search Recipes", annotations=_READ_ONLY)
async def search_recipes_by_query(
    query: str,
    category: RecipeCategory | None = None,
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
    offset = int(cursor) if cursor else 0

    embedding: list[float] | None = None
    try:
        from yes_chef_mcp.pipeline.embeddings import generate_query_embedding

        embedding = generate_query_embedding(query)
    except ImportError:
        pass  # sentence-transformers not available — FTS-only
    except OSError as exc:
        # Model not cached and can't be downloaded (e.g. offline) — FTS-only.
        logger.warning("Query embedding unavailable, falling back to keyword search: %s", exc)

    result = await hybrid_search(
        query=query,
        embedding=embedding,
        category=category,
        tags=tags,
        max_results=max_results,
        min_confidence=min_confidence,
        offset=offset,
    )

    return RecipeSearchPageSchema.model_validate(result)


@mcp.tool(title="Search Recipes by Macros", annotations=_READ_ONLY)
async def search_recipes_by_macros(
    target_calories: float | None = None,
    target_protein_g: float | None = None,
    target_carbs_g: float | None = None,
    target_fat_g: float | None = None,
    category: RecipeCategory | None = None,
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
    offset = int(cursor) if cursor else 0

    result = await macro_distance_search(
        target_calories=target_calories,
        target_protein_g=target_protein_g,
        target_carbs_g=target_carbs_g,
        target_fat_g=target_fat_g,
        category=category,
        tags=tags,
        max_results=max_results,
        tolerance_pct=tolerance_pct,
        offset=offset,
    )

    return RecipeSearchPageSchema.model_validate(result)


# ── Recipe Detail ─────────────────────────────────────────────────────────


@mcp.tool(title="Get Recipe Details", annotations=_READ_ONLY)
async def get_recipe_detail(recipe_id: str) -> RecipeDetailSchema:
    """Get complete recipe information: ingredients, instructions,
    full nutrition breakdown, and tags.

    Raises an error if no recipe has the given ID.
    """
    recipe = await get_recipe(recipe_id)
    if recipe is None:
        raise ToolError(f"Recipe not found: {recipe_id!r}")

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


@mcp.tool(title="Compose Meal", annotations=_READ_ONLY)
async def compose_meal(
    components: list[MealComponentSchema],
    member_id: str | None = None,
    target_name: str | None = None,
) -> MealCompositionSchema:
    """Compose a meal from multiple recipes and compute aggregate nutrition.

    Each component is a recipe_id plus servings (default 1.0).
    If member_id is provided, compares against their active macro target
    (or the target named target_name).
    Designed for iterative refinement — search, compose, adjust, repeat.
    """
    meal_components = [
        MealComponent(recipe_id=c.recipe_id, servings=c.servings) for c in components
    ]

    result = await _compose(meal_components, member_id, target_name)

    return MealCompositionSchema.model_validate(result)


@mcp.tool(title="Suggest Meal Complement", annotations=_READ_ONLY)
async def suggest_meal_complement(
    existing_components: list[MealComponentSchema],
    member_id: str,
    complement_category: RecipeCategory = RecipeCategory.SIDE,
    max_results: int = 5,
) -> list[ComplementSuggestionSchema]:
    """Suggest sides/additions that bring a partial meal closer to macro targets.

    existing_components is the partial meal (recipe_id plus servings each).
    Returns an empty list if the member has no active macro target.

    "I have grilled chicken — what side gets me closest to my targets?"
    """
    results = await suggest_complements(
        [c.recipe_id for c in existing_components],
        [c.servings for c in existing_components],
        member_id,
        complement_category,
        max_results,
    )

    return [ComplementSuggestionSchema.model_validate(s) for s in results]


# ── Meal Plan CRUD ───────────────────────────────────────────────────────


@mcp.tool(title="Create Meal Plan", annotations=_CREATE)
async def create_meal_plan(
    name: str,
    start_date: str,
    family_id: str,
    days: int = 7,
) -> MealPlanSchema:
    """Create an empty meal plan scaffold. start_date is ISO format (YYYY-MM-DD)."""
    plan = await _create_plan(
        family_id=family_id,
        name=name,
        start_date=date.fromisoformat(start_date),
        days=days,
    )

    return MealPlanSchema.model_validate(plan)


@mcp.tool(
    title="Add Recipe to Meal Plan",
    # Upsert: re-adding the same recipe to the same slot overwrites its servings.
    annotations=ToolAnnotations(
        readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False
    ),
)
async def add_to_meal_plan(
    plan_id: str,
    day_offset: int,
    meal_type: MealType,
    recipe_id: str,
    servings: float = 1.0,
    member_servings: dict[str, float] | None = None,
) -> list[MealSlotSchema]:
    """Add a recipe to a specific slot in the meal plan.

    If the recipe is already in that slot, its servings are replaced.
    Returns the updated day with all slots.
    """
    await add_meal_slot(plan_id, day_offset, meal_type, recipe_id, servings, member_servings)

    slots = await get_meal_slots(plan_id, day_offset)
    return [MealSlotSchema.model_validate(s) for s in slots]


@mcp.tool(title="Get Meal Plan Summary", annotations=_READ_ONLY)
async def get_meal_plan_summary(
    plan_id: str,
    member_id: str | None = None,
    day_offset: int | None = None,
    detail_level: DetailLevel = DetailLevel.DAILY,
) -> MealPlanSummarySchema:
    """Plan overview with configurable granularity.

    detail_level controls response size:
    - "weekly": just weekly averages per member vs. targets (~200 tokens)
    - "daily": per-day macro totals per member (~500 tokens)
    - "full": per-day, per-meal breakdown (~1500 tokens)

    Raises an error if the plan does not exist.
    """
    plan = await get_meal_plan(plan_id)
    if plan is None:
        raise ToolError(f"Meal plan not found: {plan_id!r}")

    slots = await get_meal_slots(plan_id, day_offset)
    nutrition_map = await get_nutrition_batch([s.recipe_id for s in slots])

    daily_summaries: list[MealPlanDaySummarySchema] = []
    days_data: dict[int, list[MealSlot]] = {}
    for s in slots:
        days_data.setdefault(s.day_offset, []).append(s)

    for day in sorted(days_data.keys()):
        day_slots = days_data[day]
        day_macros: dict[str, list[float]] = {}

        meals: dict[str, list[MealComponentSchema]] = {}
        for s in day_slots:
            nutr = nutrition_map.get(s.recipe_id)
            meal_key = s.meal_type.value

            if detail_level == DetailLevel.FULL:
                meals.setdefault(meal_key, []).append(
                    MealComponentSchema(recipe_id=s.recipe_id, servings=s.servings)
                )

            if nutr is None:
                continue

            members_to_track = [member_id] if member_id else list(s.member_servings.keys())
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
                meals=meals if detail_level == DetailLevel.FULL else {},
            )
        )

    weekly_avgs: dict[str, MacroSummarySchema] = {}
    if daily_summaries:
        all_members: set[str] = set()
        for ds in daily_summaries:
            all_members.update(ds.member_macros.keys())

        for mid in all_members:
            member_days = [
                ds.member_macros[mid] for ds in daily_summaries if mid in ds.member_macros
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
        detail_level=detail_level,
        daily_summaries=daily_summaries if detail_level != DetailLevel.WEEKLY else [],
        weekly_averages=weekly_avgs,
    )


# ── Grocery List ──────────────────────────────────────────────────────────


@mcp.tool(title="Generate Grocery List", annotations=_READ_ONLY)
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


@mcp.tool(title="List Recipe Tags", annotations=_READ_ONLY)
async def list_tags() -> list[str]:
    """List all available recipe tags for filtering."""
    return await list_all_tags()


@mcp.tool(title="List Recipe Categories", annotations=_READ_ONLY)
async def list_categories() -> list[str]:
    """List all available recipe categories."""
    return await list_all_categories()


# ── Macro Targets ─────────────────────────────────────────────────────────


@mcp.tool(title="Get Macro Targets", annotations=_READ_ONLY)
async def get_macro_targets(
    member_id: str | None = None,
) -> list[MacroTargetSchema]:
    """List macro target profiles, optionally filtered by member.

    Each target has an is_active flag; a member has at most one active target.
    """
    targets = await list_macro_targets(member_id)
    return [MacroTargetSchema.model_validate(t) for t in targets]


# ── Family & Member Management ───────────────────────────────────────────


@mcp.tool(title="List Family Members", annotations=_READ_ONLY)
async def list_family_members(
    family_id: str | None = None,
) -> list[MemberSchema]:
    """List family members, optionally filtered by family.

    Does not include macro targets — use get_macro_targets(member_id) for those.
    """
    members = await list_members(family_id)
    return [MemberSchema.model_validate(m) for m in members]


@mcp.tool(
    title="Set Macro Target",
    # Always inserts a new target; with set_active it also deactivates the
    # member's other targets, which changes existing state.
    annotations=ToolAnnotations(
        readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False
    ),
)
async def set_macro_target(
    member_id: str,
    name: str,
    calories: float,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    set_active: bool = True,
) -> MacroTargetSchema:
    """Create a new macro target for a member.

    Always adds a new target (existing targets are never edited, even with the
    same name). If set_active is true (default), the member's other targets are
    deactivated so this one becomes the active target.
    """
    target = await create_macro_target(
        member_id, name, calories, protein_g, carbs_g, fat_g, set_active
    )
    return MacroTargetSchema.model_validate(target)


# ── Optimization Tools ───────────────────────────────────────────────────


@mcp.tool(title="Optimize Meal", annotations=_READ_ONLY)
async def optimize_meal(
    member_ids: list[str],
    meal_type: MealType,
    candidate_recipe_ids: list[str] | None = None,
    required_recipe_ids: list[str] | None = None,
    excluded_recipe_ids: list[str] | None = None,
    max_components: int = 4,
    allow_fractional_servings: bool = True,
    num_alternatives: int = 3,
) -> list[OptimizedMealSchema]:
    """Find the best combination of recipes and servings for a single meal.

    Returns up to num_alternatives proposals ranked by objective score.
    Nothing is saved — use add_to_meal_plan to apply a proposal.
    """
    results = await _optimize_meal(
        member_ids=member_ids,
        meal_type=meal_type,
        candidate_recipe_ids=candidate_recipe_ids,
        required_recipe_ids=required_recipe_ids,
        excluded_recipe_ids=excluded_recipe_ids,
        max_components=max_components,
        allow_fractional_servings=allow_fractional_servings,
        num_alternatives=num_alternatives,
    )

    return [OptimizedMealSchema.model_validate(om) for om in results]


@mcp.tool(title="Optimize Meal Plan", annotations=_READ_ONLY)
async def optimize_plan(
    plan_id: str,
    member_ids: list[str],
    meal_types: list[MealType] | None = None,
    max_components_per_meal: int = 3,
) -> OptimizedPlanSchema:
    """Propose recipes for all empty slots in a meal plan across the full week.

    Returns a proposal only — the plan is not modified. Use add_to_meal_plan
    to apply the proposed slots.
    """
    result = await _optimize_plan(
        plan_id=plan_id,
        member_ids=member_ids,
        meal_types=meal_types,
        max_components_per_meal=max_components_per_meal,
    )

    return OptimizedPlanSchema.model_validate(result)


@mcp.tool(title="Rebalance Meal Plan", annotations=_READ_ONLY)
async def rebalance_plan(
    plan_id: str,
    member_id: str,
    strategy: RebalanceStrategy = RebalanceStrategy.ADJUST_SERVINGS,
) -> RebalancedPlanSchema:
    """Propose fine-tuning of an existing plan for one member.

    Returns before/after macros and the adjusted slots as a proposal — the
    plan is not modified. Use add_to_meal_plan to apply adjusted servings.

    Strategies:
    - "adjust_servings": keep all recipes, solve for optimal serving sizes
    - "swap_sides": not implemented yet — currently returns the plan unchanged
    """
    result = await _rebalance_plan(plan_id, member_id, strategy)

    return RebalancedPlanSchema.model_validate(result)


# ── View Tools (MCP Apps Extension) ─────────────────────────────────────

# Each view tool returns a ToolResult: a one-line text summary for the model,
# plus structuredContent (a *DataSchema payload) that the linked ui:// view
# renders. Hosts that support the MCP Apps extension display the HTML in a
# sandboxed iframe and push the tool result into it via the ext-apps SDK.

# Views are single-file bundles (JS/CSS inlined), so the only external origins
# left are Google Fonts (stylesheet + font files).
_VIEW_CSP = ResourceCSP(
    resource_domains=["https://fonts.googleapis.com", "https://fonts.gstatic.com"],
)


@mcp.tool(
    app=AppConfig(resource_uri="ui://yes_chef_mcp/macro-setter.html"),
    output_schema=MacroSetterDataSchema.model_json_schema(),
)
async def show_macro_target_setter(
    member_id: str | None = None,
) -> ToolResult:
    """Show an interactive macro target editor with sliders and pie chart.

    The user can adjust protein, carbs, and fat targets and see real-time
    calorie impact. When the user clicks Save, the app calls
    save_macro_targets with the new values.
    """
    targets = await get_macro_targets(member_id)
    active = next((t for t in targets if t.is_active), None)

    data = MacroSetterDataSchema(
        current_targets=MacroSetterTargetsSchema.model_validate(active) if active else None
    )

    if active:
        summary = (
            f"Showing macro target editor with active target '{active.name}': "
            f"{active.calories:.0f} kcal, {active.protein_g:.0f}g protein, "
            f"{active.carbs_g:.0f}g carbs, {active.fat_g:.0f}g fat"
        )
    else:
        summary = "Showing macro target editor (no active target; using defaults)"

    return ToolResult(content=summary, structured_content=data.model_dump(mode="json"))


@mcp.tool(
    app=AppConfig(
        resource_uri="ui://yes_chef_mcp/recipe-selector.html",
        visibility=["model"],
    ),
    output_schema=RecipeSelectorDataSchema.model_json_schema(),
)
async def show_recipe_selector(
    query: str = "",
    category: RecipeCategory | None = None,
    tags: list[str] | None = None,
    max_results: int = 20,
) -> ToolResult:
    """Show a visual recipe browser with cards, category filters, and macro badges.

    Displays search results in a responsive grid. The user selects a recipe
    and the app calls select_recipe with the chosen recipe_id.
    """
    page = await search_recipes_by_query(
        query=query,
        category=category,
        tags=tags,
        max_results=max_results,
    )
    data = RecipeSelectorDataSchema(recipes=page.hits)

    count = len(data.recipes)
    noun = "recipe" if count == 1 else "recipes"
    summary = f"Showing {count} {noun} for '{query}'" if query else f"Showing {count} {noun}"

    return ToolResult(content=summary, structured_content=data.model_dump(mode="json"))


@mcp.tool(
    app=AppConfig(resource_uri="ui://yes_chef_mcp/weekly-calendar.html"),
    output_schema=WeeklyCalendarDataSchema.model_json_schema(),
)
async def show_weekly_calendar(
    plan_id: str,
    member_id: str | None = None,
) -> ToolResult:
    """Show a 7-day meal plan calendar with macro variance indicators.

    Displays all meals per day with color-coded progress bars showing
    proximity to daily macro targets. Includes action buttons for
    optimize, rebalance, and refresh.
    """
    plan_summary = await get_meal_plan_summary(plan_id, member_id, detail_level=DetailLevel.FULL)

    targets: MacroSummarySchema | None = None
    if member_id:
        target_list = await get_macro_targets(member_id)
        active = next((t for t in target_list if t.is_active), None)
        if active:
            targets = MacroSummarySchema.model_validate(active)

    recipe_ids = list(
        dict.fromkeys(
            component.recipe_id
            for day in plan_summary.daily_summaries
            for components in day.meals.values()
            for component in components
        )
    )
    recipes = await search_by_ids(recipe_ids) if recipe_ids else None

    data = WeeklyCalendarDataSchema(
        plan_summary=plan_summary,
        targets=targets,
        recipes=[RecipeSearchHitSchema.model_validate(h) for h in recipes.hits] if recipes else [],
    )

    filled_days = len(plan_summary.daily_summaries)
    summary = (
        f"Showing {plan_summary.days}-day calendar for plan '{plan_summary.plan_name}' "
        f"({filled_days} of {plan_summary.days} days have meals)"
    )

    return ToolResult(content=summary, structured_content=data.model_dump(mode="json"))


@mcp.tool(
    app=AppConfig(resource_uri="ui://yes_chef_mcp/grocery-list.html"),
    output_schema=GroceryListDataSchema.model_json_schema(),
)
async def show_grocery_checklist(
    plan_id: str,
    merge_similar: bool = True,
    exclude_pantry: bool = True,
) -> ToolResult:
    """Show an interactive grocery checklist grouped by ingredient category.

    Users can check off items they already have in their pantry. When they
    click Confirm, the app calls confirm_grocery_list with only the
    unchecked items they need to buy.
    """
    grocery_list = await generate_grocery_list(plan_id, merge_similar, exclude_pantry)
    data = GroceryListDataSchema(grocery_list=grocery_list)

    count = len(grocery_list.items)
    categories = len({item.category for item in grocery_list.items})
    summary = f"Showing grocery checklist with {count} items across {categories} categories"

    return ToolResult(content=summary, structured_content=data.model_dump(mode="json"))


# ── UI Resources (MCP Apps) ─────────────────────────────────────────────

# Each resource serves a single-file HTML bundle from frontend/dist/views/
# as-is: all JS and CSS are inlined, so nothing loads from this server.


@mcp.resource(
    "ui://yes_chef_mcp/macro-setter.html",
    app=AppConfig(csp=_VIEW_CSP),
)
def macro_setter_resource() -> str:
    """Interactive macro target editor UI."""
    from yes_chef_mcp.api.views import read_view_html

    return read_view_html("macro-setter")


@mcp.resource(
    "ui://yes_chef_mcp/recipe-selector.html",
    app=AppConfig(csp=_VIEW_CSP),
)
def recipe_selector_resource() -> str:
    """Recipe browser with card grid UI."""
    from yes_chef_mcp.api.views import read_view_html

    return read_view_html("recipe-selector")


@mcp.resource(
    "ui://yes_chef_mcp/weekly-calendar.html",
    app=AppConfig(csp=_VIEW_CSP),
)
def weekly_calendar_resource() -> str:
    """Weekly meal plan calendar UI."""
    from yes_chef_mcp.api.views import read_view_html

    return read_view_html("weekly-calendar")


@mcp.resource(
    "ui://yes_chef_mcp/grocery-list.html",
    app=AppConfig(csp=_VIEW_CSP),
)
def grocery_list_resource() -> str:
    """Grocery checklist UI."""
    from yes_chef_mcp.api.views import read_view_html

    return read_view_html("grocery-list")
