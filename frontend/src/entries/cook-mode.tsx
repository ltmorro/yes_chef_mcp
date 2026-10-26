import { callServerTool, parseCookModeData, parseMealLogEntry, setModelContext } from "../bridge.ts";
import type { App } from "../bridge.ts";
import { mountMcpView } from "../mcpView.tsx";
import { CookModePage } from "../pages";
import type { CookModeData, CookRating } from "../types.ts";

/** Log the meal via log_cooked_meal (against the plan slot, if any), then tell the model. */
async function finish(
  app: App,
  data: CookModeData,
  canSetContext: boolean,
  rating: CookRating | null,
): Promise<string> {
  const { recipe_id, servings, plan_id, day_offset, meal_type } = data;
  const slot = plan_id !== null ? { plan_id, day_offset, meal_type } : {};
  const result = await callServerTool(app, "log_cooked_meal", {
    recipe_id,
    servings,
    ...(rating ? { rating } : {}),
    ...slot,
  });
  const entry = parseMealLogEntry(result.structuredContent);
  if (!entry) throw new Error("The meal was logged but no entry came back.");

  if (canSetContext) {
    // The log already happened; a context failure shouldn't report it as failed.
    await setModelContext(
      app,
      `The user finished cooking ${data.recipe_name} (${servings} servings)` +
        `${rating ? `, rated ${rating}` : ", no rating"}; logged as meal_log entry ${entry.id}.`,
      { meal_log_entry: { ...entry } },
    ).catch((err: unknown) => console.warn("updateModelContext failed:", err));
  }
  return "Logged. Enjoy your meal!";
}

mountMcpView({
  appName: "Cook Mode",
  parse: parseCookModeData,
  displayModes: ["inline", "fullscreen"],
  render: ({ app, data, host, display }) => (
    <CookModePage
      source={{
        data,
        finish: host.serverTools
          ? (rating) => finish(app, data, host.modelContext, rating)
          : undefined,
        display,
      }}
    />
  ),
});
