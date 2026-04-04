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

export interface GroceryList {
  plan_id: string;
  items: GroceryItem[];
}

/** View data payloads injected by the backend. */

export interface MacroSetterData {
  current_targets?: {
    protein_g: number;
    carbs_g: number;
    fat_g: number;
    calories: number;
    name: string;
  };
}

export interface RecipeSelectorData {
  recipes: RecipeHit[];
}

export interface WeeklyCalendarData {
  plan_summary: PlanSummary;
  targets?: MacroSummary;
}

export interface GroceryListData {
  grocery_list: GroceryList;
}
