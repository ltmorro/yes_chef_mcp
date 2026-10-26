/** Each view renders its tool result, shows tool errors, and hides what the host can't do. */

import { expect, openView, test } from "./fakeHost.ts";
import grocery from "./fixtures/grocery-list.json" with { type: "json" };
import macro from "./fixtures/macro-setter.json" with { type: "json" };
import recipes from "./fixtures/recipe-selector.json" with { type: "json" };
import calendar from "./fixtures/weekly-calendar.json" with { type: "json" };

test.describe("renders the tool result", () => {
  test("macro setter", async ({ page }) => {
    const host = await openView(page, "macro-setter", { toolResult: macro });
    await expect(host.view.getByText("Daily Target · Alex")).toBeVisible();
    // Sliders seeded from current_targets: 150g protein, 200g carbs, 60g fat.
    for (const grams of ["150", "200", "60"]) {
      await expect(host.view.getByText(grams, { exact: true })).toBeVisible();
    }
    await expect(host.view.getByRole("textbox", { name: "Total calories" })).toBeVisible();
    await expect(host.view.getByRole("button", { name: "Save Targets" })).toBeEnabled();
    expect(host.errors).toEqual([]);
  });

  test("recipe selector", async ({ page }) => {
    const host = await openView(page, "recipe-selector", { toolResult: recipes });
    await expect(host.view.getByText("2 recipes found")).toBeVisible();
    await expect(host.view.getByText("Lemon Chicken")).toBeVisible();
    await expect(host.view.getByText("Garlic Rice")).toBeVisible();
    await expect(host.view.getByRole("button", { name: "Use This Recipe" })).toBeDisabled();
  });

  test("weekly calendar", async ({ page }) => {
    const host = await openView(page, "weekly-calendar", { toolResult: calendar });
    await expect(host.view.getByRole("heading", { name: "Spring Week" })).toBeVisible();
    await expect(host.view.getByText("7-day plan overview")).toBeVisible();
    await expect(host.view.getByText("Lemon Chicken")).toBeVisible();
    await expect(host.view.getByText("Garlic Rice")).toBeVisible();
    await expect(host.view.getByText("No meals")).toHaveCount(5);
  });

  test("grocery list", async ({ page }) => {
    const host = await openView(page, "grocery-list", { toolResult: grocery });
    for (const item of ["rice", "garlic", "lemon", "chicken breast"]) {
      await expect(host.view.getByText(item, { exact: true })).toBeVisible();
    }
    await expect(host.view.getByText("0 of 4 items checked off")).toBeVisible();
    await expect(host.view.getByRole("button", { name: "Confirm List (4 items)" })).toBeVisible();
  });

  test("an error tool result shows the error", async ({ page }) => {
    const host = await openView(page, "weekly-calendar", {
      toolResult: { isError: true, content: [{ type: "text", text: "Meal plan not found: nope" }] },
    });
    const alert = host.view.getByRole("alert");
    await expect(alert).toContainText("Something went wrong");
    await expect(alert).toContainText("Meal plan not found: nope");
  });
});

test.describe("missing host capabilities", () => {
  test("no message: recipe confirm hidden", async ({ page }) => {
    const host = await openView(page, "recipe-selector", {
      toolResult: recipes,
      capabilities: { serverTools: {}, updateModelContext: { text: {} } },
    });
    await expect(host.view.getByText("Lemon Chicken")).toBeVisible();
    await expect(host.view.getByRole("button", { name: "Use This Recipe" })).toHaveCount(0);
  });

  test("no message: grocery confirm hidden", async ({ page }) => {
    const host = await openView(page, "grocery-list", {
      toolResult: grocery,
      capabilities: { serverTools: {}, updateModelContext: { text: {} } },
    });
    await expect(host.view.getByText("rice", { exact: true })).toBeVisible();
    await expect(host.view.getByRole("button", { name: /Confirm List|Pantry/ })).toHaveCount(0);
  });

  test("no message: calendar optimize/rebalance hidden, refresh kept", async ({ page }) => {
    const host = await openView(page, "weekly-calendar", {
      toolResult: calendar,
      capabilities: { serverTools: {} },
    });
    await expect(host.view.getByRole("button", { name: "Refresh" })).toBeVisible();
    await expect(host.view.getByRole("button", { name: "Optimize Empty Slots" })).toHaveCount(0);
    await expect(host.view.getByRole("button", { name: "Rebalance Plan" })).toHaveCount(0);
  });

  test("no serverTools: macro Save disabled", async ({ page }) => {
    const host = await openView(page, "macro-setter", {
      toolResult: macro,
      capabilities: { message: { text: {} } },
    });
    await expect(host.view.getByRole("button", { name: "Save Targets" })).toBeDisabled();
  });

  test("no updateModelContext: selecting a recipe sends no context", async ({ page }) => {
    const host = await openView(page, "recipe-selector", {
      toolResult: recipes,
      capabilities: { message: { text: {} } },
    });
    await host.view.getByText("Lemon Chicken").click();
    await expect(host.view.getByRole("button", { name: "Use This Recipe" })).toBeEnabled();
    expect(await host.messages("ui/update-model-context")).toEqual([]);
  });
});
