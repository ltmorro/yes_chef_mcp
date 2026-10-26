import { callTool, parseMacroSetterData } from "../bridge.ts";
import { mountMcpView } from "../mcpView.tsx";
import { MacroSetterPage } from "../pages";

mountMcpView({
  appName: "Macro Setter",
  parse: parseMacroSetterData,
  render: (app, data) => (
    <MacroSetterPage
      source={{
        data,
        // save_macro_targets doesn't exist on the server yet — fixed in a follow-up PR
        save: (values) => callTool(app, "save_macro_targets", { ...values }),
      }}
    />
  ),
});
