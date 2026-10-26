import { parseGroceryListData, sendUserMessage, setModelContext } from "../bridge.ts";
import type { App } from "../bridge.ts";
import { mountMcpView } from "../mcpView.tsx";
import { GroceryListPage } from "../pages";
import type { GroceryConfirmation } from "../pages";
import type { GroceryItem } from "../types.ts";

/** Items named in the chat message when the full list goes into model context. */
const MESSAGE_ITEM_LIMIT = 10;

function describeItem(item: GroceryItem): string {
  if (!item.quantity) return item.name;
  return `${item.quantity}${item.unit ? ` ${item.unit}` : ""} ${item.name}`;
}

function summarize(items: GroceryItem[], limit: number): string {
  if (items.length === 0) return "I already have everything on the grocery list.";
  const shown = items.slice(0, limit).map(describeItem);
  const more = items.length - shown.length;
  const noun = items.length === 1 ? "item" : "items";
  return `I need to buy ${items.length} ${noun}: ${shown.join(", ")}${more > 0 ? `, and ${more} more` : ""}.`;
}

/**
 * No backend storage for confirmed lists yet (AnyList export is TODO), so the
 * to-buy list goes back to the model: in full as model context, plus a short
 * chat message. Without context support, the message carries every item.
 */
async function confirm(
  app: App,
  planId: string,
  canSetContext: boolean,
  confirmation: GroceryConfirmation,
): Promise<void> {
  const { items, checked_off_count, total_count } = confirmation;
  if (canSetContext) {
    await setModelContext(
      app,
      `Confirmed shopping list for meal plan ${planId} (${items.length} of ${total_count} ` +
        `items to buy; ${checked_off_count} already in the pantry):\n` +
        items.map((item) => `- ${describeItem(item)}`).join("\n"),
      { plan_id: planId, to_buy: items, checked_off_count, total_count },
    );
  }
  await sendUserMessage(app, summarize(items, canSetContext ? MESSAGE_ITEM_LIMIT : items.length));
}

mountMcpView({
  appName: "Grocery List",
  parse: parseGroceryListData,
  render: ({ app, data, host }) => (
    <GroceryListPage
      source={{
        loading: false,
        data,
        onConfirm: host.message
          ? (confirmation) =>
              confirm(app, data.grocery_list.plan_id, host.modelContext, confirmation)
          : undefined,
      }}
    />
  ),
});
