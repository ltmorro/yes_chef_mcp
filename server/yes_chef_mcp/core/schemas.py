"""Pydantic models for API/MCP boundaries.

These handle validation and serialization at the edges.
Internal code uses the dataclass models from core.models.

All schemas use `from_attributes=True` so they can be constructed
directly from dataclass instances via `Schema.model_validate(obj)`.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from yes_chef_mcp.core.models import (
    DetailLevel,
    MatchType,
    MealType,
    MemberRole,
    NutritionSource,
    OptimizationObjective,
    ProviderType,
    RebalanceStrategy,
    RecipeCategory,
    RecipeSource,
    SolverStatus,
)


# ── Shared / Reusable ────────────────────────────────────────────────────


class MacroSummarySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    calories: float = 0.0
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0


class IngredientSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    quantity: float | None = None
    unit: str | None = None
    raw_text: str = ""
    sub_recipe_id: str | None = None


class MealComponentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recipe_id: str
    servings: float = 1.0


# ── Recipe Schemas ────────────────────────────────────────────────────────


class RecipeSearchHitSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    category: RecipeCategory | None = None
    tags: list[str] = Field(default_factory=list)
    prep_minutes: int | None = None
    cook_minutes: int | None = None
    macro_summary: MacroSummarySchema = Field(default_factory=MacroSummarySchema)
    search_score: float = 0.0
    match_type: MatchType = MatchType.KEYWORD


class RecipeSearchPageSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hits: list[RecipeSearchHitSchema] = Field(default_factory=list)
    next_cursor: str | None = None
    total_count: int = 0


class RecipeDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    family_id: str
    name: str
    source: RecipeSource
    ingredients: list[IngredientSchema] = Field(default_factory=list)
    instructions: str = ""
    servings: int = 1
    prep_minutes: int | None = None
    cook_minutes: int | None = None
    tags: list[str] = Field(default_factory=list)
    category: RecipeCategory | None = None
    image_url: str | None = None
    nutrition: NutritionSchema | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ── Nutrition ─────────────────────────────────────────────────────────────


class NutritionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recipe_id: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float = 0.0
    sodium_mg: float = 0.0
    source: NutritionSource = NutritionSource.MANUAL
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    computed_at: datetime | None = None


# ── Family & Members ─────────────────────────────────────────────────────


class FamilySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    provider: ProviderType
    created_at: datetime | None = None


class MemberSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    family_id: str
    name: str
    role: MemberRole = MemberRole.MEMBER
    is_default: bool = False
    created_at: datetime | None = None


class CreateMemberRequest(BaseModel):
    name: str
    role: MemberRole = MemberRole.MEMBER
    is_default: bool = False


# ── Macro Targets ─────────────────────────────────────────────────────────


class MacroTargetSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    member_id: str
    name: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    is_active: bool = True


class SetMacroTargetRequest(BaseModel):
    name: str
    calories: float = Field(gt=0)
    protein_g: float = Field(gt=0)
    carbs_g: float = Field(gt=0)
    fat_g: float = Field(gt=0)
    set_active: bool = True


# ── Meal Plan ─────────────────────────────────────────────────────────────


class MealPlanSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    family_id: str
    name: str
    start_date: date
    days: int = 7
    created_at: datetime | None = None


class CreateMealPlanRequest(BaseModel):
    name: str
    start_date: date
    days: int = Field(default=7, ge=1, le=14)
    family_id: str


class MealSlotSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan_id: str
    day_offset: int = Field(ge=0, le=13)
    meal_type: MealType
    recipe_id: str
    servings: float = Field(default=1.0, gt=0)
    member_servings: dict[str, float] = Field(default_factory=dict)


class AddToMealPlanRequest(BaseModel):
    day_offset: int = Field(ge=0, le=13)
    meal_type: MealType
    recipe_id: str
    servings: float = Field(default=1.0, gt=0)
    member_servings: dict[str, float] | None = None


# ── Meal Composition ─────────────────────────────────────────────────────


class ComponentNutritionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recipe_id: str
    recipe_name: str
    servings: float
    macros: MacroSummarySchema


class MealCompositionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    components: list[ComponentNutritionSchema] = Field(default_factory=list)
    totals: MacroSummarySchema = Field(default_factory=MacroSummarySchema)
    member_deltas: dict[str, MacroSummarySchema] = Field(default_factory=dict)
    suggestions: list[str] = Field(default_factory=list)


class ComposeMealRequest(BaseModel):
    components: list[MealComponentSchema]
    member_id: str | None = None
    target_name: str | None = None


class ComplementSuggestionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recipe_id: str
    recipe_name: str
    category: RecipeCategory | None = None
    suggested_servings: float
    projected_totals: MacroSummarySchema
    projected_deviation: MacroSummarySchema


# ── Grocery ───────────────────────────────────────────────────────────────


class GroceryItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    quantity: float
    unit: str | None = None
    category: str = "other"
    recipe_sources: list[str] = Field(default_factory=list)


class GroceryListSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan_id: str
    items: list[GroceryItemSchema] = Field(default_factory=list)


# ── Optimization ─────────────────────────────────────────────────────────


class MealConstraintsSchema(BaseModel):
    max_calories: float | None = None
    min_protein_g: float | None = None
    max_carbs_g: float | None = None
    max_fat_g: float | None = None
    max_prep_minutes: int | None = None
    required_tags: list[str] | None = None
    excluded_tags: list[str] | None = None
    required_categories: dict[str, int] | None = None


class PlanConstraintsSchema(BaseModel):
    max_recipe_repeats: int = Field(default=2, ge=1)
    category_requirements: dict[str, dict[str, int]] | None = None
    prep_time_budget: int | None = None
    tag_preferences: dict[str, float] | None = None
    excluded_recipe_ids: list[str] | None = None
    day_constraints: dict[int, MealConstraintsSchema] | None = None


class PinnedSlotSchema(BaseModel):
    day_offset: int = Field(ge=0, le=13)
    meal_type: MealType
    recipe_id: str
    member_servings: dict[str, float]


class OptimizeMealRequest(BaseModel):
    member_ids: list[str]
    meal_type: MealType
    candidate_recipe_ids: list[str] | None = None
    required_recipe_ids: list[str] | None = None
    excluded_recipe_ids: list[str] | None = None
    constraints: MealConstraintsSchema | None = None
    objective: OptimizationObjective = OptimizationObjective.MINIMIZE_DEVIATION
    max_components: int = Field(default=4, ge=1, le=10)
    allow_fractional_servings: bool = True
    num_alternatives: int = Field(default=3, ge=1, le=10)


class OptimizePlanRequest(BaseModel):
    plan_id: str
    member_ids: list[str]
    meal_types: list[MealType] = Field(
        default_factory=lambda: [MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER]
    )
    pinned_slots: list[PinnedSlotSchema] | None = None
    constraints: PlanConstraintsSchema | None = None
    objective: OptimizationObjective = OptimizationObjective.MINIMIZE_DEVIATION
    max_components_per_meal: int = Field(default=3, ge=1, le=10)


class RebalancePlanRequest(BaseModel):
    plan_id: str
    member_id: str
    strategy: RebalanceStrategy = RebalanceStrategy.ADJUST_SERVINGS


class SolverResultSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: SolverStatus
    relaxations_applied: list[str] = Field(default_factory=list)
    objective_score: float = 0.0
    solve_time_ms: int = 0
    gap_pct: float | None = None


class OptimizedMealSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recipes: list[MealComponentSchema] = Field(default_factory=list)
    member_servings: dict[str, dict[str, float]] = Field(default_factory=dict)
    member_macros: dict[str, MacroSummarySchema] = Field(default_factory=dict)
    member_deviation: dict[str, MacroSummarySchema] = Field(default_factory=dict)
    objective_score: float = 0.0
    solve_time_ms: int = 0
    solver_result: SolverResultSchema | None = None


class OptimizedPlanSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan_id: str
    slots: list[MealSlotSchema] = Field(default_factory=list)
    daily_summaries: dict[str, dict[int, MacroSummarySchema]] = Field(default_factory=dict)
    weekly_summaries: dict[str, MacroSummarySchema] = Field(default_factory=dict)
    total_deviation: float = 0.0
    recipe_usage_counts: dict[str, int] = Field(default_factory=dict)
    solve_time_ms: int = 0
    solver_result: SolverResultSchema | None = None


class RebalancedPlanSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan_id: str
    member_id: str
    strategy: RebalanceStrategy
    before_macros: dict[int, MacroSummarySchema] = Field(default_factory=dict)
    after_macros: dict[int, MacroSummarySchema] = Field(default_factory=dict)
    adjusted_slots: list[MealSlotSchema] = Field(default_factory=list)
    solver_result: SolverResultSchema | None = None


# ── Meal Plan Summary ────────────────────────────────────────────────────


class MealPlanDaySummarySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day_offset: int
    member_macros: dict[str, MacroSummarySchema] = Field(default_factory=dict)
    meals: dict[str, list[MealComponentSchema]] = Field(default_factory=dict)


class MealPlanSummarySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan_id: str
    plan_name: str
    start_date: date
    days: int
    detail_level: DetailLevel
    daily_summaries: list[MealPlanDaySummarySchema] = Field(default_factory=list)
    weekly_averages: dict[str, MacroSummarySchema] = Field(default_factory=dict)
