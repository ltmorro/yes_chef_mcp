import { callTool, parseGroceryListData } from "../bridge.ts";
import { mountMcpView } from "../mcpView.tsx";
import { GroceryListPage } from "../pages";

mountMcpView({
  appName: "Grocery List",
  parse: parseGroceryListData,
  render: (app, data) => (
    <GroceryListPage
      source={{
        loading: false,
        data,
        // confirm_grocery_list doesn't exist on the server yet — fixed in a follow-up PR
        onConfirm: (confirmation) => callTool(app, "confirm_grocery_list", { ...confirmation }),
      }}
    />
  ),
});
