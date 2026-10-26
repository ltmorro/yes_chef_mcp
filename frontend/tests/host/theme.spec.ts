/** Host theming (theme + style variables) and the fullscreen toggle. */

import { expect, openView, test } from "./fakeHost.ts";
import type { FakeHost, HostContext } from "./fakeHost.ts";
import macro from "./fixtures/macro-setter.json" with { type: "json" };
import calendar from "./fixtures/weekly-calendar.json" with { type: "json" };

// A host palette given as light-dark(), so a theme flip alone changes the colors.
const HOST_VARS = {
  "--color-background-primary": "light-dark(#ffffff, #262624)",
  "--color-text-primary": "light-dark(#141413, #faf9f5)",
};

const DARK: HostContext = {
  theme: "dark",
  displayMode: "inline",
  availableDisplayModes: ["inline", "fullscreen"],
  styles: { variables: HOST_VARS },
};

const html = (host: FakeHost) => host.view.locator("html");
const body = (host: FakeHost) => host.view.locator("body");

test("dark host context applies; host-context-changed to light updates it", async ({ page }) => {
  const host = await openView(page, "macro-setter", { toolResult: macro, hostContext: DARK });
  await expect(html(host)).toHaveAttribute("data-theme", "dark");
  await expect(body(host)).toHaveCSS("background-color", "rgb(38, 38, 36)");
  await expect(body(host)).toHaveCSS("color", "rgb(250, 249, 245)");

  await host.notify("ui/notifications/host-context-changed", { theme: "light" });
  await expect(html(host)).toHaveAttribute("data-theme", "light");
  await expect(body(host)).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(body(host)).toHaveCSS("color", "rgb(20, 20, 19)");
});

test.describe("fullscreen toggle", () => {
  test("hidden when the host doesn't offer fullscreen", async ({ page }) => {
    const host = await openView(page, "weekly-calendar", {
      toolResult: calendar,
      hostContext: { theme: "light", availableDisplayModes: ["inline"] },
    });
    await expect(host.view.getByRole("heading", { name: "Spring Week" })).toBeVisible();
    await expect(host.view.getByRole("button", { name: /Fullscreen/ })).toHaveCount(0);
  });

  test("hidden on a view that only supports inline", async ({ page }) => {
    const host = await openView(page, "macro-setter", { toolResult: macro, hostContext: DARK });
    await expect(host.view.getByRole("button", { name: "Save Targets" })).toBeVisible();
    await expect(host.view.getByRole("button", { name: /Fullscreen/ })).toHaveCount(0);
    const init = await host.waitFor("ui/initialize");
    expect(init.params).toMatchObject({ appCapabilities: { availableDisplayModes: ["inline"] } });
  });

  test("requests the display mode; the label follows the returned mode", async ({ page }) => {
    const host = await openView(page, "weekly-calendar", { toolResult: calendar, hostContext: DARK });
    const init = await host.waitFor("ui/initialize");
    expect(init.params).toMatchObject({
      appCapabilities: { availableDisplayModes: ["inline", "fullscreen"] },
    });

    await host.view.getByRole("button", { name: "Fullscreen", exact: true }).click();
    const request = await host.waitFor("ui/request-display-mode");
    expect(request.params).toEqual({ mode: "fullscreen" });
    const exit = host.view.getByRole("button", { name: "Exit Fullscreen" });
    await expect(exit).toBeVisible();

    await host.clearMessages();
    await exit.click();
    const back = await host.waitFor("ui/request-display-mode");
    expect(back.params).toEqual({ mode: "inline" });
    await expect(host.view.getByRole("button", { name: "Fullscreen", exact: true })).toBeVisible();
  });

  test("a rejected request shows feedback and re-enables the button", async ({ page }) => {
    const host = await openView(page, "weekly-calendar", {
      toolResult: calendar,
      hostContext: DARK,
      displayMode: { error: "Fullscreen is not allowed here" },
    });
    const toggle = host.view.getByRole("button", { name: "Fullscreen", exact: true });
    await toggle.click();
    await expect(host.view.getByRole("alert")).toContainText(
      "Error: Couldn't switch to fullscreen: ",
    );
    await expect(host.view.getByRole("alert")).toContainText("Fullscreen is not allowed here");
    await expect(toggle).toBeEnabled();
  });

  test("a host that keeps another mode says so", async ({ page }) => {
    const host = await openView(page, "weekly-calendar", {
      toolResult: calendar,
      hostContext: DARK,
      displayMode: { mode: "inline" },
    });
    await host.view.getByRole("button", { name: "Fullscreen", exact: true }).click();
    await expect(host.view.getByText("The host kept the view inline.")).toBeVisible();
    await expect(host.view.getByRole("button", { name: "Fullscreen", exact: true })).toBeEnabled();
  });
});
