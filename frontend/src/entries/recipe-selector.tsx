import { parseRecipeSelectorData, sendUserMessage, setModelContext } from "../bridge.ts";
import type { App } from "../bridge.ts";
import { mountMcpView } from "../mcpView.tsx";
import { RecipeSelectorPage } from "../pages";
import type { RecipeHit } from "../types.ts";

/** Keep the model aware of what's selected, without prompting a reply. */
function reportSelection(app: App, recipe: RecipeHit | null): void {
  const text = recipe
    ? `In the recipe browser the user has selected ${recipe.name} (id ${recipe.id}), ` +
      "but hasn't confirmed it yet."
    : "In the recipe browser the user has no recipe selected.";
  const selected = recipe ? { id: recipe.id, name: recipe.name } : null;
  setModelContext(app, text, { selected_recipe: selected }).catch((err: unknown) =>
    console.warn("updateModelContext failed:", err),
  );
}

mountMcpView({
  appName: "Recipe Selector",
  parse: parseRecipeSelectorData,
  // No write tool: the choice goes back to the model, which decides what to do with it.
  render: ({ app, data, host }) => (
    <RecipeSelectorPage
      source={{
        data,
        onSelectionChange: host.modelContext
          ? (recipe) => reportSelection(app, recipe)
          : undefined,
        onConfirm: host.message
          ? (recipe) => sendUserMessage(app, `Selected recipe: ${recipe.name} (id ${recipe.id})`)
          : undefined,
      }}
    />
  ),
});
