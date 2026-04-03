"""Internal domain models using dataclasses.

These are used throughout the core library. Pydantic models at the edges
(API/MCP) convert to/from these via schemas.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


# ── Enums ──────────────────────────────────────────────────────────────────


class RecipeSource(StrEnum):
    ANYLIST = "anylist"
    MEALIE = "mealie"
    CSV = "csv"
    PAPRIKA = "paprika"
    MANUAL = "manual"


class RecipeCategory(StrEnum):
    MAIN = "main"
    SIDE = "side"
    SNACK = "snack"
    DESSERT = "dessert"
    BREAKFAST = "breakfast"


class NutritionSource(StrEnum):
    USDA = "usda"
    NUTRITIONIX = "nutritionix"
    MANUAL = "manual"


class MealType(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class MemberRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"


class ProviderType(StrEnum):
    ANYLIST = "anylist"
    MEALIE = "mealie"
    CSV = "csv"
    PAPRIKA = "paprika"


class DetailLevel(StrEnum):
    WEEKLY = "weekly"
    DAILY = "daily"
    FULL = "full"


class RebalanceStrategy(StrEnum):
    ADJUST_SERVINGS = "adjust_servings"
    SWAP_SIDES = "swap_sides"


class OptimizationObjective(StrEnum):
    MINIMIZE_DEVIATION = "minimize_deviation"
    MAXIMIZE_PROTEIN = "maximize_protein"
    MINIMIZE_CALORIES = "minimize_calories"
    MAXIMIZE_VARIETY = "maximize_variety"


class SolverStatus(StrEnum):
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    RELAXED = "relaxed"
    HEURISTIC = "heuristic"


class PerishabilityTier(StrEnum):
    """How quickly an ingredient spoils after purchase."""

    HIGH = "high"  # 1-4 days: fresh herbs, berries, fish
    MEDIUM = "medium"  # 5-10 days: milk, yogurt, fresh meat, soft cheese
    LOW = "low"  # 11-21 days: eggs, hard cheese, root vegetables
    STABLE = "stable"  # 21+ days or shelf-stable: canned, dried, frozen


class MatchType(StrEnum):
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    BOTH = "both"


# ── Ingredient ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Ingredient:
    name: str
    quantity: float | None = None
    unit: str | None = None
    raw_text: str = ""
    sub_recipe_id: str | None = None


# ── Recipe ─────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class Recipe:
    id: str
    family_id: str
    name: str
    source: RecipeSource
    ingredients: list[Ingredient] = field(default_factory=list)
    instructions: str = ""
    servings: int = 1
    prep_minutes: int | None = None
    cook_minutes: int | None = None
    tags: list[str] = field(default_factory=list)
    category: RecipeCategory | None = None
    image_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ── Nutrition ──────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class MacroSummary:
    calories: float = 0.0
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0


@dataclass(slots=True)
class Nutrition:
    recipe_id: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float = 0.0
    sodium_mg: float = 0.0
    source: NutritionSource = NutritionSource.MANUAL
    confidence: float = 0.0
    computed_at: datetime | None = None


# ── Family & Members ──────────────────────────────────────────────────────


@dataclass(slots=True)
class Family:
    id: str
    name: str
    provider: ProviderType
    provider_config: dict[str, str] = field(default_factory=dict)
    created_at: datetime | None = None


@dataclass(slots=True)
class Member:
    id: str
    family_id: str
    name: str
    role: MemberRole = MemberRole.MEMBER
    is_default: bool = False
    created_at: datetime | None = None


# ── Macro Targets ─────────────────────────────────────────────────────────


@dataclass(slots=True)
class MacroTarget:
    id: str
    member_id: str
    name: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    is_active: bool = True


@dataclass(slots=True)
class MacroTargetOverride:
    target_id: str
    day_of_week: int  # 0=Mon, 6=Sun (ISO)
    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    label: str = ""


# ── Meal Plan ─────────────────────────────────────────────────────────────


@dataclass(slots=True)
class MealPlan:
    id: str
    family_id: str
    name: str
    start_date: date
    days: int = 7
    created_at: datetime | None = None


@dataclass(slots=True)
class MealSlot:
    plan_id: str
    day_offset: int
    meal_type: MealType
    recipe_id: str
    servings: float = 1.0
    member_servings: dict[str, float] = field(default_factory=dict)


# ── Search Results ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RecipeSearchHit:
    id: str
    name: str
    category: RecipeCategory | None
    tags: list[str]
    prep_minutes: int | None
    cook_minutes: int | None
    macro_summary: MacroSummary
    search_score: float
    match_type: MatchType


@dataclass(slots=True)
class RecipeSearchPage:
    hits: list[RecipeSearchHit] = field(default_factory=list)
    next_cursor: str | None = None
    total_count: int = 0


# ── Meal Composition ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class MealComponent:
    recipe_id: str
    servings: float = 1.0


@dataclass(slots=True)
class ComponentNutrition:
    recipe_id: str
    recipe_name: str
    servings: float
    macros: MacroSummary


@dataclass(slots=True)
class MealComposition:
    components: list[ComponentNutrition] = field(default_factory=list)
    totals: MacroSummary = field(default_factory=MacroSummary)
    member_deltas: dict[str, MacroSummary] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ComplementSuggestion:
    recipe_id: str
    recipe_name: str
    category: RecipeCategory | None
    suggested_servings: float
    projected_totals: MacroSummary
    projected_deviation: MacroSummary


# ── Grocery ───────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class GroceryItem:
    name: str
    quantity: float
    unit: str | None = None
    category: str = "other"
    recipe_sources: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GroceryList:
    plan_id: str
    items: list[GroceryItem] = field(default_factory=list)


# ── Spoilage ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SpoilageProfile:
    """Perishability metadata for an ingredient."""

    ingredient_name: str
    tier: PerishabilityTier
    shelf_life_days: int
    typical_unit: str | None = None


@dataclass(frozen=True, slots=True)
class SpoilageConfig:
    """Tuning knobs for spoilage-aware optimization.

    spoilage_weight controls how much ingredient overlap affects scoring
    relative to macro deviation. Kept intentionally small so the hierarchy
    stays calorie → macro → spoilage.
    """

    spoilage_weight: float = 0.10
    overlap_bonus_per_shared: float = 0.02
    high_tier_multiplier: float = 1.0
    medium_tier_multiplier: float = 0.5
    low_tier_multiplier: float = 0.15
    stable_tier_multiplier: float = 0.0


# ── Optimization ──────────────────────────────────────────────────────────


@dataclass(slots=True)
class MealConstraints:
    max_calories: float | None = None
    min_protein_g: float | None = None
    max_carbs_g: float | None = None
    max_fat_g: float | None = None
    max_prep_minutes: int | None = None
    required_tags: list[str] | None = None
    excluded_tags: list[str] | None = None
    required_categories: dict[str, int] | None = None


@dataclass(slots=True)
class PlanConstraints:
    max_recipe_repeats: int = 2
    category_requirements: dict[str, dict[str, int]] | None = None
    prep_time_budget: int | None = None
    tag_preferences: dict[str, float] | None = None
    excluded_recipe_ids: list[str] | None = None
    day_constraints: dict[int, MealConstraints] | None = None


@dataclass(frozen=True, slots=True)
class PinnedSlot:
    day_offset: int
    meal_type: MealType
    recipe_id: str
    member_servings: dict[str, float]


@dataclass(slots=True)
class SolverResult:
    status: SolverStatus
    relaxations_applied: list[str] = field(default_factory=list)
    objective_score: float = 0.0
    solve_time_ms: int = 0
    gap_pct: float | None = None


@dataclass(slots=True)
class OptimizedMeal:
    recipes: list[MealComponent] = field(default_factory=list)
    member_servings: dict[str, dict[str, float]] = field(default_factory=dict)
    member_macros: dict[str, MacroSummary] = field(default_factory=dict)
    member_deviation: dict[str, MacroSummary] = field(default_factory=dict)
    objective_score: float = 0.0
    solve_time_ms: int = 0
    solver_result: SolverResult | None = None


@dataclass(slots=True)
class OptimizedPlan:
    plan_id: str
    slots: list[MealSlot] = field(default_factory=list)
    daily_summaries: dict[str, dict[int, MacroSummary]] = field(default_factory=dict)
    weekly_summaries: dict[str, MacroSummary] = field(default_factory=dict)
    total_deviation: float = 0.0
    recipe_usage_counts: dict[str, int] = field(default_factory=dict)
    solve_time_ms: int = 0
    solver_result: SolverResult | None = None


@dataclass(slots=True)
class RebalancedPlan:
    plan_id: str
    member_id: str
    strategy: RebalanceStrategy
    before_macros: dict[int, MacroSummary] = field(default_factory=dict)
    after_macros: dict[int, MacroSummary] = field(default_factory=dict)
    adjusted_slots: list[MealSlot] = field(default_factory=list)
    solver_result: SolverResult | None = None


# ── Meal Plan Summary ────────────────────────────────────────────────────


@dataclass(slots=True)
class MealPlanDaySummary:
    day_offset: int
    member_macros: dict[str, MacroSummary] = field(default_factory=dict)
    meals: dict[str, list[MealComponent]] = field(default_factory=dict)


@dataclass(slots=True)
class MealPlanSummary:
    plan_id: str
    plan_name: str
    start_date: date
    days: int
    detail_level: DetailLevel
    daily_summaries: list[MealPlanDaySummary] = field(default_factory=list)
    weekly_averages: dict[str, MacroSummary] = field(default_factory=dict)
