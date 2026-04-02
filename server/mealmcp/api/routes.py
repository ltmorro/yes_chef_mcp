"""FastAPI REST and WebSocket routes."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from mealmcp.core.models import (
    DetailLevel,
    MealComponent,
    MealType,
    OptimizationObjective,
    RebalanceStrategy,
    RecipeCategory,
)
from mealmcp.core.schemas import (
    AddToMealPlanRequest,
    ComposeMealRequest,
    CreateMealPlanRequest,
    CreateMemberRequest,
    GroceryListSchema,
    MacroSummarySchema,
    MealCompositionSchema,
    MealPlanSchema,
    MealPlanSummarySchema,
    MealSlotSchema,
    MacroTargetSchema,
    MemberSchema,
    OptimizeMealRequest,
    OptimizedMealSchema,
    RebalancePlanRequest,
    RebalancedPlanSchema,
    RecipeDetailSchema,
    RecipeSearchPageSchema,
    SetMacroTargetRequest,
)

router = APIRouter()


# ── Recipes ───────────────────────────────────────────────────────────────


@router.get("/recipes", response_model=RecipeSearchPageSchema)
async def search_recipes(
    q: str = "",
    category: str | None = None,
    tags: str | None = None,
    max_results: int = 20,
    cursor: str | None = None,
) -> RecipeSearchPageSchema:
    """Search recipes by query string."""
    from mealmcp.core.search import hybrid_search

    cat = RecipeCategory(category) if category else None
    tag_list = tags.split(",") if tags else None
    offset = int(cursor) if cursor else 0

    result = hybrid_search(
        query=q,
        category=cat,
        tags=tag_list,
        max_results=max_results,
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


@router.get("/recipes/{recipe_id}", response_model=RecipeDetailSchema)
async def get_recipe(recipe_id: str) -> RecipeDetailSchema:
    """Get full recipe detail."""
    from mealmcp.core.recipe_store import get_nutrition, get_recipe as _get

    recipe = _get(recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")

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


@router.post("/meals/compose", response_model=MealCompositionSchema)
async def compose_meal_route(request: ComposeMealRequest) -> MealCompositionSchema:
    """Compose a meal from multiple recipes."""
    from mealmcp.core.meal_composer import compose_meal

    components = [
        MealComponent(recipe_id=c.recipe_id, servings=c.servings)
        for c in request.components
    ]

    result = compose_meal(components, request.member_id, request.target_name)

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
                calories=d.calories, protein_g=d.protein_g,
                carbs_g=d.carbs_g, fat_g=d.fat_g,
            )
            for mid, d in result.member_deltas.items()
        },
        suggestions=result.suggestions,
    )


# ── Meal Plans ────────────────────────────────────────────────────────────


@router.get("/plans", response_model=list[MealPlanSchema])
async def list_plans(family_id: str | None = None) -> list[MealPlanSchema]:
    """List meal plans."""
    from mealmcp.core.planner import list_meal_plans

    plans = list_meal_plans(family_id)
    return [
        MealPlanSchema(
            id=p.id, family_id=p.family_id, name=p.name,
            start_date=p.start_date, days=p.days, created_at=p.created_at,
        )
        for p in plans
    ]


@router.post("/plans", response_model=MealPlanSchema)
async def create_plan(request: CreateMealPlanRequest) -> MealPlanSchema:
    """Create a new meal plan."""
    from mealmcp.core.planner import create_meal_plan

    plan = create_meal_plan(
        family_id=request.family_id,
        name=request.name,
        start_date=request.start_date,
        days=request.days,
    )
    return MealPlanSchema(
        id=plan.id, family_id=plan.family_id, name=plan.name,
        start_date=plan.start_date, days=plan.days, created_at=plan.created_at,
    )


@router.get("/plans/{plan_id}", response_model=MealPlanSchema)
async def get_plan(plan_id: str) -> MealPlanSchema:
    """Get a meal plan."""
    from mealmcp.core.planner import get_meal_plan

    plan = get_meal_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return MealPlanSchema(
        id=plan.id, family_id=plan.family_id, name=plan.name,
        start_date=plan.start_date, days=plan.days, created_at=plan.created_at,
    )


@router.get("/plans/{plan_id}/summary", response_model=MealPlanSummarySchema)
async def get_plan_summary(
    plan_id: str,
    member_id: str | None = None,
    day: int | None = None,
    detail: str = "daily",
) -> MealPlanSummarySchema:
    """Get meal plan summary."""
    from mealmcp.mcp.server import get_meal_plan_summary

    return await get_meal_plan_summary(plan_id, member_id, day, detail)


@router.put("/plans/{plan_id}/slots", response_model=list[MealSlotSchema])
async def add_slot(
    plan_id: str,
    request: AddToMealPlanRequest,
) -> list[MealSlotSchema]:
    """Add a recipe to a meal plan slot."""
    from mealmcp.mcp.server import add_to_meal_plan

    return await add_to_meal_plan(
        plan_id, request.day_offset, request.meal_type.value,
        request.recipe_id, request.servings, request.member_servings,
    )


@router.delete("/plans/{plan_id}/slots/{day_offset}/{meal_type}/{recipe_id}")
async def remove_slot(
    plan_id: str, day_offset: int, meal_type: str, recipe_id: str
) -> dict[str, bool]:
    """Remove a recipe from a meal plan slot."""
    from mealmcp.core.planner import remove_meal_slot

    mt = MealType(meal_type)
    removed = remove_meal_slot(plan_id, day_offset, mt, recipe_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Slot not found")
    return {"removed": True}


@router.post("/plans/{plan_id}/rebalance", response_model=RebalancedPlanSchema)
async def rebalance_plan_route(
    plan_id: str, request: RebalancePlanRequest
) -> RebalancedPlanSchema:
    """Rebalance a meal plan for a member."""
    from mealmcp.mcp.server import rebalance_plan

    return await rebalance_plan(plan_id, request.member_id, request.strategy.value)


@router.get("/plans/{plan_id}/grocery-list", response_model=GroceryListSchema)
async def get_grocery_list(
    plan_id: str,
    merge_similar: bool = True,
    exclude_pantry: bool = True,
) -> GroceryListSchema:
    """Generate grocery list from a meal plan."""
    from mealmcp.mcp.server import generate_grocery_list

    return await generate_grocery_list(plan_id, merge_similar, exclude_pantry)


# ── Optimization ──────────────────────────────────────────────────────────


@router.post("/meals/optimize", response_model=list[OptimizedMealSchema])
async def optimize_meal_route(
    request: OptimizeMealRequest,
) -> list[OptimizedMealSchema]:
    """Optimize a single meal."""
    from mealmcp.mcp.server import optimize_meal

    return await optimize_meal(
        member_ids=request.member_ids,
        meal_type=request.meal_type.value,
        candidate_recipe_ids=request.candidate_recipe_ids,
        required_recipe_ids=request.required_recipe_ids,
        excluded_recipe_ids=request.excluded_recipe_ids,
        max_components=request.max_components,
        allow_fractional_servings=request.allow_fractional_servings,
        num_alternatives=request.num_alternatives,
    )


# ── Members & Targets ────────────────────────────────────────────────────


@router.get("/families/{family_id}/members", response_model=list[MemberSchema])
async def get_members(family_id: str) -> list[MemberSchema]:
    """List family members."""
    from mealmcp.mcp.server import list_family_members

    return await list_family_members(family_id)


@router.post("/families/{family_id}/members", response_model=MemberSchema)
async def create_member(
    family_id: str, request: CreateMemberRequest
) -> MemberSchema:
    """Create a new family member."""
    import uuid

    from mealmcp.core.db import get_cursor

    member_id = str(uuid.uuid4())
    with get_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO members (id, family_id, name, role, is_default)
            VALUES (?, ?, ?, ?, ?)
            """,
            (member_id, family_id, request.name, request.role.value, int(request.is_default)),
        )

    return MemberSchema(
        id=member_id,
        family_id=family_id,
        name=request.name,
        role=request.role,
        is_default=request.is_default,
    )


@router.get("/members/{member_id}/targets", response_model=list[MacroTargetSchema])
async def get_member_targets(member_id: str) -> list[MacroTargetSchema]:
    """Get macro targets for a member."""
    from mealmcp.mcp.server import get_macro_targets

    return await get_macro_targets(member_id)


@router.post("/members/{member_id}/targets", response_model=MacroTargetSchema)
async def create_target(
    member_id: str, request: SetMacroTargetRequest
) -> MacroTargetSchema:
    """Create a macro target for a member."""
    from mealmcp.mcp.server import set_macro_target

    return await set_macro_target(
        member_id=member_id,
        name=request.name,
        calories=request.calories,
        protein_g=request.protein_g,
        carbs_g=request.carbs_g,
        fat_g=request.fat_g,
        set_active=request.set_active,
    )


# ── WebSocket ─────────────────────────────────────────────────────────────


@router.websocket("/ws/plan/{plan_id}")
async def plan_websocket(websocket: WebSocket, plan_id: str) -> None:
    """WebSocket endpoint for real-time plan updates."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back for now — real implementation would broadcast plan changes
            await websocket.send_text(f"Plan {plan_id}: received {data}")
    except WebSocketDisconnect:
        pass
