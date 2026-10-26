import {
  callServerTool,
  parseMacroSetterData,
  parseMacroTarget,
  setModelContext,
} from "../bridge.ts";
import type { App } from "../bridge.ts";
import { mountMcpView } from "../mcpView.tsx";
import { MacroSetterPage } from "../pages";
import type { MacroValues } from "../pages";
import type { MacroSetterData, MacroTarget } from "../types.ts";

/** Write directly via set_macro_target (as the new active target), then tell the model. */
async function save(
  app: App,
  data: MacroSetterData,
  canSetContext: boolean,
  values: MacroValues,
): Promise<MacroTarget> {
  const result = await callServerTool(app, "set_macro_target", {
    member_id: data.member_id,
    name: data.target_name,
    ...values,
    set_active: true,
  });
  const saved = parseMacroTarget(result.structuredContent);
  if (!saved) throw new Error("The save succeeded but returned no target.");

  if (canSetContext) {
    // The save already happened; a context failure shouldn't report it as failed.
    await setModelContext(
      app,
      `${data.member_name}'s active macro target is now "${saved.name}": ` +
        `${Math.round(saved.calories)} kcal, ${Math.round(saved.protein_g)}g protein, ` +
        `${Math.round(saved.carbs_g)}g carbs, ${Math.round(saved.fat_g)}g fat ` +
        `(target id ${saved.id}, saved from the macro target editor).`,
      { member_id: data.member_id, active_target: { ...saved } },
    ).catch((err: unknown) => console.warn("updateModelContext failed:", err));
  }
  return saved;
}

mountMcpView({
  appName: "Macro Setter",
  parse: parseMacroSetterData,
  render: ({ app, data, host }) => (
    <MacroSetterPage
      source={{
        data,
        save: host.serverTools
          ? (values) => save(app, data, host.modelContext, values)
          : undefined,
      }}
    />
  ),
});
