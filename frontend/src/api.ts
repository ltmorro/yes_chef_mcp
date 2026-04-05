/**
 * API client for the Yes Chef SPA frontend.
 *
 * Fetches data from the FastAPI REST endpoints instead of reading
 * injected JSON (which is the MCP entry approach).
 */

import type {
  GroceryList,
  MacroSummary,
  MacroTarget,
  PlanSummary,
  RecipeHit,
} from "./types.ts";

const API_BASE = "/api";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

/* ── Recipes ─────────────────��───────────────────────────────────────── */

interface RecipeSearchResponse {
  hits: RecipeHit[];
  next_cursor: string | null;
  total_count: number;
}

export async function fetchRecipes(
  q?: string,
  category?: string,
  tags?: string[],
  maxResults = 20,
): Promise<RecipeHit[]> {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (category) params.set("category", category);
  if (tags?.length) params.set("tags", tags.join(","));
  params.set("max_results", String(maxResults));

  const result = await apiFetch<RecipeSearchResponse>(`/recipes?${params}`);
  return result.hits;
}

/* ── Macro Targets ────────��──────────────────────────────────────────── */

export async function fetchMacroTargets(
  memberId?: string,
): Promise<MacroTarget[]> {
  if (!memberId) return [];
  return apiFetch<MacroTarget[]>(`/members/${memberId}/targets`);
}

export async function saveMacroTarget(
  memberId: string,
  target: { name?: string; calories: number; protein_g: number; carbs_g: number; fat_g: number },
): Promise<MacroTarget> {
  return apiFetch<MacroTarget>(`/members/${memberId}/targets`, {
    method: "POST",
    body: JSON.stringify({ ...target, set_active: true }),
  });
}

/* ── Meal Plans ──────��──────────────────────────���────────────────────── */

interface MealPlanListItem {
  id: string;
  family_id: string;
  name: string;
  start_date: string;
  days: number;
}

export async function fetchPlans(): Promise<MealPlanListItem[]> {
  return apiFetch<MealPlanListItem[]>("/plans");
}

export async function fetchPlanSummary(
  planId: string,
  memberId?: string,
): Promise<PlanSummary> {
  const params = new URLSearchParams({ detail: "full" });
  if (memberId) params.set("member_id", memberId);
  return apiFetch<PlanSummary>(`/plans/${planId}/summary?${params}`);
}

/* ── Grocery ───���─────────────────────────────��───────────────────────── */

export async function fetchGroceryList(
  planId: string,
  mergeSimilar = true,
  excludePantry = true,
): Promise<GroceryList> {
  const params = new URLSearchParams({
    merge_similar: String(mergeSimilar),
    exclude_pantry: String(excludePantry),
  });
  return apiFetch<GroceryList>(`/plans/${planId}/grocery-list?${params}`);
}

/* ── Members ��────────────────────────────���───────────────────────────── */

interface FamilyMember {
  id: string;
  family_id: string;
  name: string;
  role: string;
  is_default: boolean;
  active_target: MacroSummary | null;
}

export async function fetchFamilyMembers(
  familyId: string,
): Promise<FamilyMember[]> {
  return apiFetch<FamilyMember[]>(`/families/${familyId}/members`);
}
