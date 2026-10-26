/**
 * MCP Apps bridge: connects a view to its MCP host via the ext-apps SDK.
 *
 * Each MCP view is rendered by the host after a show_* tool call. The host
 * pushes that tool's result to us (`ui/notifications/tool-result`); we read
 * its `structuredContent` (the view payload) and render it. Button actions
 * go back through the host with `app.callServerTool(...)`.
 */

import { useState } from "react";
import { useApp } from "@modelcontextprotocol/ext-apps/react";
import type { App } from "@modelcontextprotocol/ext-apps";
import type { CallToolResult } from "@modelcontextprotocol/client";
import type {
  GroceryListData,
  MacroSetterData,
  RecipeSelectorData,
  WeeklyCalendarData,
} from "./types.ts";

export type { App };

export type McpViewState<T> =
  | { status: "connecting" }
  | { status: "error"; message: string }
  | { status: "waiting"; app: App }
  | { status: "ready"; app: App; data: T };

/** Narrows a tool result's structuredContent to a view payload, or null if it doesn't fit. */
export type PayloadParser<T> = (structuredContent: unknown) => T | null;

function firstText(result: CallToolResult): string | null {
  for (const block of result.content) {
    if (block.type === "text") return block.text;
  }
  return null;
}

/**
 * Create and connect an ext-apps `App`, and track the latest tool result.
 *
 * The tool-result handler is registered in `onAppCreated`, i.e. before
 * `connect()`, so the initial result the host sends right after the
 * handshake is never missed.
 */
export function useMcpView<T>(appName: string, parse: PayloadParser<T>): McpViewState<T> {
  const [data, setData] = useState<T | null>(null);
  const [resultError, setResultError] = useState<string | null>(null);

  const { app, isConnected, error } = useApp({
    appInfo: { name: appName, version: "0.1.0" },
    capabilities: {},
    onAppCreated: (created) => {
      created.ontoolresult = (result) => {
        if (result.isError) {
          setResultError(firstText(result) ?? "The tool call failed.");
          return;
        }
        const parsed = parse(result.structuredContent);
        if (parsed === null) {
          setResultError("The tool result did not include the data this view needs.");
          return;
        }
        setResultError(null);
        setData(parsed);
      };
      created.ontoolcancelled = () => {
        setResultError("The tool call was cancelled.");
      };
    },
  });

  if (error) return { status: "error", message: `Couldn't connect to the MCP host: ${error.message}` };
  if (!app || !isConnected) return { status: "connecting" };
  if (resultError) return { status: "error", message: resultError };
  if (data === null) return { status: "waiting", app };
  return { status: "ready", app, data };
}

/** Fire-and-forget a server tool call through the host, logging failures. */
export function callTool(app: App, name: string, args: Record<string, unknown>): void {
  app.callServerTool({ name, arguments: args }).then(
    (result) => {
      if (result.isError) console.error(`Tool ${name} failed:`, firstText(result));
    },
    (err: unknown) => console.error(`Tool ${name} failed:`, err),
  );
}

/* ── Payload parsers ─────────────────────────────────────────────────────
 * Shallow shape checks at the trust boundary. The backend validates the full
 * payload against its Pydantic schema (and advertises it as outputSchema), so
 * here we only guard against a missing or wrong-tool payload; the `as` casts
 * below are that trust boundary. */

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export const parseMacroSetterData: PayloadParser<MacroSetterData> = (value) => {
  if (!isRecord(value)) return null;
  const targets = value.current_targets;
  if (targets === null || targets === undefined) return { current_targets: null };
  if (!isRecord(targets) || typeof targets.protein_g !== "number") return null;
  return value as unknown as MacroSetterData;
};

export const parseRecipeSelectorData: PayloadParser<RecipeSelectorData> = (value) => {
  if (!isRecord(value) || !Array.isArray(value.recipes)) return null;
  return value as unknown as RecipeSelectorData;
};

export const parseWeeklyCalendarData: PayloadParser<WeeklyCalendarData> = (value) => {
  if (!isRecord(value) || !isRecord(value.plan_summary) || !Array.isArray(value.recipes)) {
    return null;
  }
  return value as unknown as WeeklyCalendarData;
};

export const parseGroceryListData: PayloadParser<GroceryListData> = (value) => {
  if (!isRecord(value) || !isRecord(value.grocery_list)) return null;
  if (!Array.isArray(value.grocery_list.items)) return null;
  return value as unknown as GroceryListData;
};
