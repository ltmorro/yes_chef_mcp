"""FastAPI REST and WebSocket routes."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from mealmcp.core.db import get_db
from mealmcp.core.meal_composer import compose_meal
from mealmcp.core.models import (
    DetailLevel,
    MealComponent,
    MealType,
    OptimizationObjective,
    RebalanceStrategy,
    RecipeCategory,
)
from mealmcp.core.planner import (
    create_meal_plan,
    get_meal_plan,
    list_meal_plans,
    remove_meal_slot,
)
from mealmcp.core.recipe_store import get_nutrition, get_recipe
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
from mealmcp.core.search import hybrid_search
from mealmcp.mcp.server import (
    add_to_meal_plan,
    generate_grocery_list,
    get_macro_targets,
    get_meal_plan_summary,
    list_family_members,
    optimize_meal,
    rebalance_plan,
    set_macro_target,
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
    cat = RecipeCategory(category) if category else None
    tag_list = tags.split(",") if tags else None
    offset = int(cursor) if cursor else 0

    result = await hybrid_search(
        query=q,
        category=cat,
        tags=tag_list,
        max_results=max_results,
        offset=offset,
    )

    return RecipeSearchPageSchema.model_validate(result)


@router.get("/recipes/{recipe_id}", response_model=RecipeDetailSchema)
async def get_recipe_route(recipe_id: str) -> RecipeDetailSchema:
    """Get full recipe detail."""
    recipe = await get_recipe(recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")

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


@router.post("/meals/compose", response_model=MealCompositionSchema)
async def compose_meal_route(request: ComposeMealRequest) -> MealCompositionSchema:
    """Compose a meal from multiple recipes."""
    components = [
        MealComponent(recipe_id=c.recipe_id, servings=c.servings)
        for c in request.components
    ]

    result = await compose_meal(components, request.member_id, request.target_name)

    return MealCompositionSchema.model_validate(result)


# ── Meal Plans ────────────────────────────────────────────────────────────


@router.get("/plans", response_model=list[MealPlanSchema])
async def list_plans(family_id: str | None = None) -> list[MealPlanSchema]:
    """List meal plans."""
    plans = await list_meal_plans(family_id)
    return [MealPlanSchema.model_validate(p) for p in plans]


@router.post("/plans", response_model=MealPlanSchema)
async def create_plan(request: CreateMealPlanRequest) -> MealPlanSchema:
    """Create a new meal plan."""
    plan = await create_meal_plan(
        family_id=request.family_id,
        name=request.name,
        start_date=request.start_date,
        days=request.days,
    )
    return MealPlanSchema.model_validate(plan)


@router.get("/plans/{plan_id}", response_model=MealPlanSchema)
async def get_plan(plan_id: str) -> MealPlanSchema:
    """Get a meal plan."""
    plan = await get_meal_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return MealPlanSchema.model_validate(plan)


@router.get("/plans/{plan_id}/summary", response_model=MealPlanSummarySchema)
async def get_plan_summary(
    plan_id: str,
    member_id: str | None = None,
    day: int | None = None,
    detail: str = "daily",
) -> MealPlanSummarySchema:
    """Get meal plan summary."""
    return await get_meal_plan_summary(plan_id, member_id, day, detail)


@router.put("/plans/{plan_id}/slots", response_model=list[MealSlotSchema])
async def add_slot(
    plan_id: str,
    request: AddToMealPlanRequest,
) -> list[MealSlotSchema]:
    """Add a recipe to a meal plan slot."""
    return await add_to_meal_plan(
        plan_id, request.day_offset, request.meal_type.value,
        request.recipe_id, request.servings, request.member_servings,
    )


@router.delete("/plans/{plan_id}/slots/{day_offset}/{meal_type}/{recipe_id}")
async def remove_slot(
    plan_id: str, day_offset: int, meal_type: str, recipe_id: str
) -> dict[str, bool]:
    """Remove a recipe from a meal plan slot."""
    mt = MealType(meal_type)
    removed = await remove_meal_slot(plan_id, day_offset, mt, recipe_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Slot not found")
    return {"removed": True}


@router.post("/plans/{plan_id}/rebalance", response_model=RebalancedPlanSchema)
async def rebalance_plan_route(
    plan_id: str, request: RebalancePlanRequest
) -> RebalancedPlanSchema:
    """Rebalance a meal plan for a member."""
    return await rebalance_plan(plan_id, request.member_id, request.strategy.value)


@router.get("/plans/{plan_id}/grocery-list", response_model=GroceryListSchema)
async def get_grocery_list(
    plan_id: str,
    merge_similar: bool = True,
    exclude_pantry: bool = True,
) -> GroceryListSchema:
    """Generate grocery list from a meal plan."""
    return await generate_grocery_list(plan_id, merge_similar, exclude_pantry)


# ── Optimization ──────────────────────────────────────────────────────────


@router.post("/meals/optimize", response_model=list[OptimizedMealSchema])
async def optimize_meal_route(
    request: OptimizeMealRequest,
) -> list[OptimizedMealSchema]:
    """Optimize a single meal."""
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
    return await list_family_members(family_id)


@router.post("/families/{family_id}/members", response_model=MemberSchema)
async def create_member(
    family_id: str, request: CreateMemberRequest
) -> MemberSchema:
    """Create a new family member."""
    member_id = str(uuid.uuid4())
    async with get_db() as db:
        await db.execute(
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
    return await get_macro_targets(member_id)


@router.post("/members/{member_id}/targets", response_model=MacroTargetSchema)
async def create_target(
    member_id: str, request: SetMacroTargetRequest
) -> MacroTargetSchema:
    """Create a macro target for a member."""
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
            await websocket.send_text(f"Plan {plan_id}: received {data}")
    except WebSocketDisconnect:
        pass
