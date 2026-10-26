/**
 * SPA calendar (REST source): the plan renders without waiting for recipe
 * enrichment, survives a failed enrichment, and ignores enrichment for a plan
 * that is no longer selected. /api is mocked with page.route; no backend.
 */

import type { Page, Route } from "@playwright/test";
import { expect, test } from "./fakeHost.ts";

const PLANS = [
  { id: "p1", family_id: "f", name: "Plan One", start_date: "2026-10-26", days: 7 },
  { id: "p2", family_id: "f", name: "Plan Two", start_date: "2026-10-26", days: 7 },
];

// Plan Two shares r1 with Plan One, so stale Plan One hits would show up on it.
const MEALS: Record<string, Record<string, { recipe_id: string; servings: number }[]>> = {
  p1: { dinner: [{ recipe_id: "r1", servings: 1 }] },
  p2: { lunch: [{ recipe_id: "r2", servings: 1 }], dinner: [{ recipe_id: "r1", servings: 1 }] },
};

function summary(id: string) {
  return {
    plan_id: id,
    plan_name: PLANS.find((p) => p.id === id)?.name,
    start_date: "2026-10-26",
    days: 7,
    detail_level: "full",
    daily_summaries: [{ day_offset: 0, member_macros: {}, meals: MEALS[id] }],
    weekly_averages: {},
  };
}

function hits(...recipes: [string, string][]) {
  return {
    hits: recipes.map(([id, name]) => ({
      id,
      name,
      category: "main",
      tags: [],
      prep_minutes: 10,
      cook_minutes: 10,
      macro_summary: { calories: 400, protein_g: 40, carbs_g: 30, fat_g: 10 },
    })),
    next_cursor: null,
    total_count: recipes.length,
  };
}

type RecipesMode = "hold" | "reject";

/** Mock the REST API; recipe requests are held (returned for the test to answer) or rejected. */
async function openCalendar(page: Page, mode: RecipesMode): Promise<Route[]> {
  const held: Route[] = [];
  await page.route("**/api/**", (route) => {
    const url = new URL(route.request().url());
    const plan = /^\/api\/plans\/(\w+)\/summary$/.exec(url.pathname);
    if (url.pathname === "/api/plans") return route.fulfill({ json: PLANS });
    if (plan?.[1]) return route.fulfill({ json: summary(plan[1]) });
    if (url.pathname === "/api/recipes" && url.searchParams.has("ids")) {
      if (mode === "reject") return route.fulfill({ status: 500, body: "boom" });
      held.push(route);
      return;
    }
    return route.fulfill({ json: [] });
  });
  await page.goto("/views/static/app.html");
  await page.getByRole("button", { name: "Calendar" }).first().click();
  return held;
}

const heading = (page: Page, name: string) => page.getByRole("heading", { name, exact: true });

test("renders the plan while the recipe request is still pending", async ({ page }) => {
  const held = await openCalendar(page, "hold");
  await expect(heading(page, "Plan One")).toBeVisible();
  await expect(page.getByText("r1", { exact: true })).toBeVisible(); // fallback card
  await expect.poll(() => held.length).toBe(1);
});

test("a rejected recipe request keeps the summary and fallback cards", async ({ page }) => {
  let rejected = false;
  page.on("requestfinished", (req) => {
    if (req.url().includes("/api/recipes?ids=")) rejected = true;
  });
  await openCalendar(page, "reject");
  await expect.poll(() => rejected).toBe(true);
  await expect(heading(page, "Plan One")).toBeVisible();
  await expect(page.getByText("r1", { exact: true })).toBeVisible();
});

test("late recipe hits enrich the cards", async ({ page }) => {
  const held = await openCalendar(page, "hold");
  await expect(page.getByText("r1", { exact: true })).toBeVisible();
  await expect.poll(() => held.length).toBe(1);
  await held[0]?.fulfill({ json: hits(["r1", "Lemon Chicken"]) });
  await expect(page.getByText("Lemon Chicken")).toBeVisible();
  await expect(page.getByText("r1", { exact: true })).toHaveCount(0);
  await expect(heading(page, "Plan One")).toBeVisible();
});

test("switching plans before enrichment ignores the old plan's response", async ({ page }) => {
  const held = await openCalendar(page, "hold");
  await expect(heading(page, "Plan One")).toBeVisible();
  await expect.poll(() => held.length).toBe(1);

  await page.getByRole("button", { name: "Plan Two" }).click();
  await expect(heading(page, "Plan Two")).toBeVisible();
  await expect.poll(() => held.length).toBe(2);

  // Plan One's enrichment arrives late: it must not touch Plan Two. (Checked
  // before Plan Two's own hits land, which would overwrite a stale update.)
  const staleResponse = page.waitForResponse((res) => res.url().endsWith("ids=r1"));
  await held[0]?.fulfill({ json: hits(["r1", "Stale Chicken"]) });
  await staleResponse;
  await page.waitForTimeout(250); // let a (buggy) stale update render
  await expect(heading(page, "Plan Two")).toBeVisible();
  await expect(page.getByText("r1", { exact: true })).toBeVisible();
  await expect(page.getByText("Stale Chicken")).toHaveCount(0);

  await held[1]?.fulfill({ json: hits(["r1", "Lemon Chicken"], ["r2", "Garlic Rice"]) });
  await expect(page.getByText("Lemon Chicken")).toBeVisible();
  await expect(page.getByText("Garlic Rice")).toBeVisible();
  await expect(page.getByText("Stale Chicken")).toHaveCount(0);
});
