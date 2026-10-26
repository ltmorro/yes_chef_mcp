import { callTool, parseRecipeSelectorData } from "../bridge.ts";
import { mountMcpView } from "../mcpView.tsx";
import { RecipeSelectorPage } from "../pages";

mountMcpView({
  appName: "Recipe Selector",
  parse: parseRecipeSelectorData,
  render: (app, data) => (
    <RecipeSelectorPage
      source={{
        data,
        // select_recipe doesn't exist on the server yet — fixed in a follow-up PR
        onViewDetails: (recipe) =>
          callTool(app, "select_recipe", { recipe_id: recipe.id, recipe_name: recipe.name }),
      }}
    />
  ),
});
