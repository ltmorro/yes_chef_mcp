/** Shared domain types matching the Python Pydantic schemas. */

export interface MacroSummary {
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

export interface MacroTarget extends MacroSummary {
  id: string;
  member_id: string;
  name: string;
  is_active: boolean;
}

export interface RecipeHit {
  id: string;
  name: string;
  category: string | null;
  tags: string[];
  prep_minutes: number | null;
  cook_minutes: number | null;
  macro_summary: MacroSummary;
}

export interface MealComponent {
  recipe_id: string;
  recipe_name?: string;
  servings: number;
}

export interface DaySummary {
  day_offset: number;
  member_macros: Record<string, MacroSummary>;
  meals: Record<string, MealComponent[]>;
}

export interface PlanSummary {
  plan_id: string;
  plan_name: string;
  start_date: string;
  days: number;
  detail_level: string;
  daily_summaries: DaySummary[];
  weekly_averages: Record<string, MacroSummary>;
}

export interface GroceryItem {
  name: string;
  quantity: number;
  unit: string | null;
  category: string;
  recipe_sources: string[];
}

export interface Ingredient {
  name: string;
  quantity: number | null;
  unit: string | null;
}

export type MealType = "breakfast" | "lunch" | "dinner" | "snack";

export interface CookStep {
  /** 1-based, as shown to the cook. */
  index: number;
  text: string;
  timer_seconds: number | null;
}

export type CookRating = "good" | "okay" | "bad";

/** structuredContent of log_cooked_meal (a MealLogEntrySchema). */
export interface MealLogEntry {
  id: string;
  recipe_id: string;
  servings: number;
  cooked_at: string;
  rating: CookRating | null;
}

export interface GroceryList {
  plan_id: string;
  items: GroceryItem[];
}

/**
 * View payloads: the structuredContent of the show_* MCP view tools.
 * Mirrors the *DataSchema Pydantic models in backend core/schemas.py.
 * The SPA builds the same shapes from REST responses.
 */

export interface MacroSetterTargets {
  name: string;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

export interface MacroSetterData {
  /** The member being edited; saves go to this member. */
  member_id: string;
  member_name: string;
  /** Name new targets are saved under. */
  target_name: string;
  current_targets: MacroSetterTargets | null;
}

export interface RecipeSelectorData {
  recipes: RecipeHit[];
}

export interface WeeklyCalendarData {
  plan_id: string;
  /** Whose targets the calendar compares against; null for no member. */
  member_id: string | null;
  plan_summary: PlanSummary;
  targets: MacroSummary | null;
  /** Hits for every recipe referenced by the plan. */
  recipes: RecipeHit[];
}

export interface GroceryListData {
  grocery_list: GroceryList;
}

export interface CookModeData {
  recipe_id: string;
  recipe_name: string;
  /** Servings being cooked; ingredient quantities are already scaled to this. */
  servings: number;
  base_servings: number;
  ingredients: Ingredient[];
  steps: CookStep[];
  /** The plan slot being cooked, if any; Done logs against it. */
  plan_id: string | null;
  day_offset: number | null;
  meal_type: MealType | null;
}

/** Progress of a button action, shown next to the button. */
export type ActionState =
  | { kind: "idle" }
  | { kind: "pending"; message: string }
  | { kind: "done"; message: string }
  | { kind: "error"; message: string };
