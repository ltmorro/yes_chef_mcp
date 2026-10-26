/** Button actions: the protocol messages each view sends, and what it shows afterwards. */

import { expect, openView, test, textOf, toolCall } from "./fakeHost.ts";
import grocery from "./fixtures/grocery-list.json" with { type: "json" };
import macro from "./fixtures/macro-setter.json" with { type: "json" };
import recipes from "./fixtures/recipe-selector.json" with { type: "json" };
import savedTarget from "./fixtures/set-macro-target.json" with { type: "json" };
import calendarNoMember from "./fixtures/weekly-calendar-nomember.json" with { type: "json" };
import refreshedCalendar from "./fixtures/weekly-calendar-refreshed.json" with { type: "json" };
import calendar from "./fixtures/weekly-calendar.json" with { type: "json" };

const NOT_CONFIRMED = /not (yet )?confirmed|hasn't confirmed|has not confirmed/i;

test.describe("macro setter Save", () => {
  test("calls set_macro_target, then updates model context", async ({ page }) => {
    const host = await openView(page, "macro-setter", {
      toolResult: macro,
      tools: { set_macro_target: savedTarget },
    });
    await host.view.getByRole("button", { name: "Save Targets" }).click();

    const context = await host.waitFor("ui/update-model-context");
    const [call] = await host.messages("tools/call");
    expect(toolCall(call)).toEqual({
      name: "set_macro_target",
      arguments: {
        member_id: "m1",
        name: "Cut",
        calories: 1940,
        protein_g: 150,
        carbs_g: 200,
        fat_g: 60,
        set_active: true,
      },
    });
    const methods = (await host.messages()).map((m) => m.method);
    expect(methods.indexOf("tools/call")).toBeLessThan(methods.indexOf("ui/update-model-context"));
    // The context describes the target the server returned, not the slider values.
    expect(textOf(context)).toContain(`Alex's active macro target is now "Cut": 2165 kcal`);
    expect(context.params.structuredContent).toMatchObject({
      member_id: "m1",
      active_target: { name: "Cut", calories: 2165 },
    });
    // (The sliders' <output>s are status regions too, so match by text.)
    await expect(host.view.getByText('Saved "Cut" as the active target: 2165 kcal')).toBeVisible();
  });

  test("a failed call shows the error and sends no context update", async ({ page }) => {
    const host = await openView(page, "macro-setter", {
      toolResult: macro,
      tools: {
        set_macro_target: {
          isError: true,
          content: [{ type: "text", text: "Member not found: 'm1'" }],
        },
      },
    });
    await host.view.getByRole("button", { name: "Save Targets" }).click();
    await expect(host.view.getByRole("alert")).toHaveText("Error: Member not found: 'm1'");
    await host.waitFor("tools/call");
    expect(await host.messages("ui/update-model-context")).toEqual([]);
    await expect(host.view.getByRole("button", { name: "Save Targets" })).toBeEnabled();
  });
});

test.describe("recipe selector", () => {
  test("selecting reports the recipe without claiming it is unconfirmed", async ({ page }) => {
    const host = await openView(page, "recipe-selector", { toolResult: recipes });
    await host.clearMessages();
    await host.view.getByText("Lemon Chicken").click();

    const context = await host.waitFor("ui/update-model-context");
    expect(textOf(context)).toContain("Lemon Chicken (id r1)");
    expect(textOf(context)).not.toMatch(NOT_CONFIRMED);
    expect(context.params.structuredContent).toEqual({
      selected_recipe: { id: "r1", name: "Lemon Chicken" },
    });
  });

  test('"Use This Recipe" sends a user message with name and id', async ({ page }) => {
    const host = await openView(page, "recipe-selector", { toolResult: recipes });
    await host.view.getByText("Garlic Rice").click();
    await host.view.getByRole("button", { name: "Use This Recipe" }).click();

    const message = await host.waitFor("ui/message");
    expect(message.params).toMatchObject({ role: "user" });
    expect(textOf(message)).toBe("Selected recipe: Garlic Rice (id r2)");
    expect(await host.messages("tools/call")).toEqual([]);
    await expect(host.view.getByRole("status")).toContainText(
      'Sent "Garlic Rice" to the conversation.',
    );
  });

  test("confirm works on a host with message but no updateModelContext", async ({ page }) => {
    const host = await openView(page, "recipe-selector", {
      toolResult: recipes,
      capabilities: { message: { text: {} } },
    });
    await host.view.getByText("Lemon Chicken").click();
    await host.view.getByRole("button", { name: "Use This Recipe" }).click();
    const message = await host.waitFor("ui/message");
    expect(textOf(message)).toBe("Selected recipe: Lemon Chicken (id r1)");
    expect(await host.messages("ui/update-model-context")).toEqual([]);
  });

  test("rapid select-then-confirm leaves no 'not confirmed' context behind", async ({ page }) => {
    const host = await openView(page, "recipe-selector", { toolResult: recipes });
    await host.view.getByText("Garlic Rice").click();
    await host.view.getByText("Lemon Chicken").click();
    await host.view.getByRole("button", { name: "Use This Recipe" }).click();

    await host.waitFor("ui/message");
    const contexts = await host.messages("ui/update-model-context");
    const last = contexts.at(-1);
    if (!last) throw new Error("expected a model context update");
    expect(textOf(last)).toContain("Lemon Chicken");
    for (const context of contexts) expect(textOf(context)).not.toMatch(NOT_CONFIRMED);
  });

  test("Clear reports that nothing is selected", async ({ page }) => {
    const host = await openView(page, "recipe-selector", { toolResult: recipes });
    await host.view.getByText("Lemon Chicken").click();
    await host.waitFor("ui/update-model-context");
    await host.clearMessages();
    await host.view.getByRole("button", { name: "Clear" }).click();
    const context = await host.waitFor("ui/update-model-context");
    expect(context.params.structuredContent).toEqual({ selected_recipe: null });
  });
});

test("grocery confirm: context with the to-buy list, then a user message", async ({ page }) => {
  const host = await openView(page, "grocery-list", { toolResult: grocery });
  await host.view.getByText("rice", { exact: true }).click(); // already in the pantry
  await host.view.getByRole("button", { name: "Confirm List (3 items)" }).click();

  const message = await host.waitFor("ui/message");
  const [context] = await host.messages("ui/update-model-context");
  if (!context) throw new Error("expected a model context update");
  const methods = (await host.messages()).map((m) => m.method);
  expect(methods.indexOf("ui/update-model-context")).toBeLessThan(methods.indexOf("ui/message"));

  expect(context.params.structuredContent).toMatchObject({
    plan_id: "plan-spring",
    checked_off_count: 1,
    total_count: 4,
    to_buy: [{ name: "garlic" }, { name: "lemon" }, { name: "chicken breast" }],
  });
  expect(textOf(context)).toContain("- 2 lb chicken breast");
  expect(textOf(context)).not.toContain("rice");
  expect(textOf(message)).toBe("I need to buy 3 items: 3 cloves garlic, 1 lemon, 2 lb chicken breast.");
  await expect(host.view.getByRole("status")).toContainText(
    "Sent your shopping list (3 items) to the conversation.",
  );
});

test.describe("weekly calendar", () => {
  test("Refresh calls show_weekly_calendar and re-renders the result", async ({ page }) => {
    const host = await openView(page, "weekly-calendar", {
      toolResult: calendar,
      tools: { show_weekly_calendar: refreshedCalendar },
    });
    await expect(host.view.getByText("Garlic Rice")).toHaveCount(1);
    await host.view.getByRole("button", { name: "Refresh" }).click();

    const call = await host.waitFor("tools/call");
    expect(toolCall(call)).toEqual({
      name: "show_weekly_calendar",
      arguments: { plan_id: "plan-spring", member_id: "m1" },
    });
    // The refreshed plan has a Wednesday lunch of Garlic Rice.
    await expect(host.view.getByText("Garlic Rice")).toHaveCount(2);
    await expect(host.view.getByText("No meals")).toHaveCount(4);
    await expect(host.view.getByRole("status")).toContainText("Plan refreshed.");
  });

  test("Optimize and Rebalance ask the model via ui/message", async ({ page }) => {
    const host = await openView(page, "weekly-calendar", { toolResult: calendar });
    await host.view.getByRole("button", { name: "Optimize Empty Slots" }).click();
    const optimize = await host.waitFor("ui/message");
    expect(textOf(optimize)).toMatch(/plan_id plan-spring.*optimize_plan for member_id m1/);
    await expect(host.view.getByRole("status")).toContainText("Asked for proposals");

    await host.clearMessages();
    await host.view.getByRole("button", { name: "Rebalance Plan" }).click();
    const rebalance = await host.waitFor("ui/message");
    expect(textOf(rebalance)).toMatch(/plan_id plan-spring.*member_id m1 using rebalance_plan/);
    expect(await host.messages("tools/call")).toEqual([]);
  });

  test("without a member, Rebalance is disabled and Refresh omits member_id", async ({ page }) => {
    const host = await openView(page, "weekly-calendar", {
      toolResult: calendarNoMember,
      tools: { show_weekly_calendar: calendarNoMember },
    });
    await expect(host.view.getByRole("button", { name: "Rebalance Plan" })).toBeDisabled();
    await expect(host.view.getByText("Rebalancing needs a family member")).toBeVisible();
    await host.view.getByRole("button", { name: "Refresh" }).click();
    const call = await host.waitFor("tools/call");
    expect(toolCall(call)).toEqual({
      name: "show_weekly_calendar",
      arguments: { plan_id: "plan-spring" },
    });
  });

  test("a rejected message shows the error", async ({ page }) => {
    const host = await openView(page, "weekly-calendar", {
      toolResult: calendar,
      message: { error: "User declined" },
    });
    await host.view.getByRole("button", { name: "Optimize Empty Slots" }).click();
    await expect(host.view.getByRole("alert")).toContainText("User declined");
  });
});
