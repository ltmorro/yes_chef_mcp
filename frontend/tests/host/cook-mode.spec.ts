/** Cook mode: stepping through, timers, the ingredient sheet, fullscreen, and Done. */

import { expect, openView, test, textOf, toolCall } from "./fakeHost.ts";
import cook from "./fixtures/cook-mode.json" with { type: "json" };
import logged from "./fixtures/log-cooked-meal.json" with { type: "json" };

test("steps advance with Next and Back, then Finish shows the rating", async ({ page }) => {
  const host = await openView(page, "cook-mode", { toolResult: cook });
  const v = host.view;
  await expect(v.getByRole("heading", { name: "Lemon Chicken" })).toBeVisible();
  await expect(v.getByText("3 servings · Step 1 of 3")).toBeVisible();
  await expect(v.getByText("Pat the chicken dry and season it.")).toBeVisible();
  await expect(v.getByText("Sear for 5 minutes per side.")).toBeHidden();
  await expect(v.getByRole("button", { name: "Back" })).toBeDisabled();

  await v.getByRole("button", { name: "Next" }).click();
  await expect(v.getByText("Sear for 5 minutes per side.")).toBeVisible();
  await expect(v.getByText("Pat the chicken dry and season it.")).toBeHidden();
  await v.getByRole("button", { name: "Back" }).click();
  await expect(v.getByText("Pat the chicken dry and season it.")).toBeVisible();

  await v.getByRole("button", { name: "Next" }).click();
  await v.getByRole("button", { name: "Next" }).click();
  await v.getByRole("button", { name: "Finish" }).click();
  await expect(v.getByText("All done!")).toBeVisible();
  await expect(v.getByRole("radio", { name: "🙂 Good" })).toBeVisible();
  await expect(v.getByRole("button", { name: "Done" })).toBeEnabled();
  expect(host.errors).toEqual([]);
});

test("the ingredient sheet shows quantities scaled to the servings", async ({ page }) => {
  const host = await openView(page, "cook-mode", { toolResult: cook });
  await host.view.getByRole("button", { name: "Ingredients (2)" }).click();

  const sheet = host.view.getByRole("dialog", { name: "Ingredients" });
  // A 1-serving recipe cooked for 3: 2 lb → 6 lb, 1 lemon → 3.
  await expect(sheet.getByText("6 lb chicken breast")).toBeVisible();
  await expect(sheet.getByText("3 lemon", { exact: true })).toBeVisible();
  await sheet.getByRole("button", { name: "Close" }).click();
  await expect(sheet).toHaveCount(0);
});

test("a timer counts down, keeps running on other steps, and resets", async ({ page }) => {
  await page.clock.install();
  const host = await openView(page, "cook-mode", { toolResult: cook });
  const v = host.view;
  await v.getByRole("button", { name: "Next" }).click();

  await v.getByRole("button", { name: "▶ Start timer · 5:00" }).click();
  await page.clock.runFor(60_000);
  await expect(v.getByRole("button", { name: "⏸ Pause · 4:00" })).toBeVisible();

  // Move on and come back: the step-2 timer kept going.
  await v.getByRole("button", { name: "Next" }).click();
  await page.clock.runFor(60_000);
  await v.getByRole("button", { name: "Back" }).click();
  await expect(v.getByRole("button", { name: "⏸ Pause · 3:00" })).toBeVisible();

  await v.getByRole("button", { name: "⏸ Pause · 3:00" }).click();
  await page.clock.runFor(60_000);
  await expect(v.getByRole("button", { name: "▶ Resume · 3:00" })).toBeVisible();

  await v.getByRole("button", { name: "▶ Resume · 3:00" }).click();
  await page.clock.runFor(181_000);
  await v.getByRole("button", { name: "⏰ Time's up · Reset" }).click();
  await expect(v.getByRole("button", { name: "▶ Start timer · 5:00" })).toBeVisible();
});

test("Done logs the meal against the slot, then updates model context", async ({ page }) => {
  const host = await openView(page, "cook-mode", {
    toolResult: cook,
    tools: { log_cooked_meal: logged },
  });
  const v = host.view;
  for (let i = 0; i < 3; i++) await v.getByRole("button", { name: /^(Next|Finish)$/ }).click();
  await v.getByRole("radio", { name: "🙂 Good" }).click();
  await v.getByRole("button", { name: "Done" }).click();

  const context = await host.waitFor("ui/update-model-context");
  const [call] = await host.messages("tools/call");
  expect(toolCall(call)).toEqual({
    name: "log_cooked_meal",
    arguments: {
      recipe_id: "r1",
      servings: 3,
      rating: "good",
      plan_id: "plan-spring",
      day_offset: 0,
      meal_type: "dinner",
    },
  });
  expect(textOf(context)).toContain("finished cooking Lemon Chicken (3 servings), rated good");
  await expect(v.getByRole("status")).toHaveText("Logged. Enjoy your meal!");
  await expect(v.getByRole("button", { name: "Done" })).toBeDisabled();
});

test("Done without a rating sends no rating", async ({ page }) => {
  const host = await openView(page, "cook-mode", {
    toolResult: cook,
    tools: { log_cooked_meal: logged },
  });
  for (let i = 0; i < 3; i++) await host.view.getByRole("button", { name: /^(Next|Finish)$/ }).click();
  await host.view.getByRole("button", { name: "Done" }).click();

  const call = await host.waitFor("tools/call");
  expect(toolCall(call).arguments).not.toHaveProperty("rating");
});

test("a failed log shows the error and sends no context update", async ({ page }) => {
  const host = await openView(page, "cook-mode", {
    toolResult: cook,
    tools: {
      log_cooked_meal: { isError: true, content: [{ type: "text", text: "Recipe not found: 'r1'" }] },
    },
  });
  for (let i = 0; i < 3; i++) await host.view.getByRole("button", { name: /^(Next|Finish)$/ }).click();
  await host.view.getByRole("button", { name: "Done" }).click();

  await expect(host.view.getByRole("alert")).toHaveText("Error: Recipe not found: 'r1'");
  expect(await host.messages("ui/update-model-context")).toEqual([]);
  await expect(host.view.getByRole("button", { name: "Done" })).toBeEnabled();
});

test("no serverTools: Done is hidden", async ({ page }) => {
  const host = await openView(page, "cook-mode", {
    toolResult: cook,
    capabilities: { message: { text: {} } },
  });
  for (let i = 0; i < 3; i++) await host.view.getByRole("button", { name: /^(Next|Finish)$/ }).click();
  await expect(host.view.getByText("All done!")).toBeVisible();
  await expect(host.view.getByRole("button", { name: "Done" })).toHaveCount(0);
});

test.describe("fullscreen", () => {
  test("requested on open when the host offers it", async ({ page }) => {
    const host = await openView(page, "cook-mode", {
      toolResult: cook,
      hostContext: { theme: "light", availableDisplayModes: ["inline", "fullscreen"] },
    });
    const request = await host.waitFor("ui/request-display-mode");
    expect(request.params).toEqual({ mode: "fullscreen" });
    await expect(host.view.getByRole("button", { name: "Exit Fullscreen" })).toBeVisible();
  });

  test("a refusal keeps the view inline with the toggle", async ({ page }) => {
    const host = await openView(page, "cook-mode", {
      toolResult: cook,
      hostContext: { theme: "light", availableDisplayModes: ["inline", "fullscreen"] },
      displayMode: { error: "Not now" },
    });
    await host.waitFor("ui/request-display-mode");
    await expect(host.view.getByRole("button", { name: "Fullscreen", exact: true })).toBeVisible();
    await expect(host.view.getByText("Pat the chicken dry and season it.")).toBeVisible();
    expect((await host.messages("ui/request-display-mode")).length).toBe(1);
  });

  test("not requested when the host is inline-only", async ({ page }) => {
    const host = await openView(page, "cook-mode", { toolResult: cook });
    await expect(host.view.getByText("3 servings · Step 1 of 3")).toBeVisible();
    expect(await host.messages("ui/request-display-mode")).toEqual([]);
  });
});
