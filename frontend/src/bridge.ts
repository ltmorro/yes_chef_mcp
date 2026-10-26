/**
 * MCP Apps bridge: connects a view to its MCP host via the ext-apps SDK.
 *
 * Each MCP view is rendered by the host after a show_* tool call. The host
 * pushes that tool's result to us (`ui/notifications/tool-result`); we read
 * its `structuredContent` (the view payload) and render it.
 *
 * Button actions go back through the host in one of three ways:
 * - `callServerTool`: run a server tool directly (writes, refreshes);
 * - `sendUserMessage`: hand the decision back to the model as a chat message;
 * - `setModelContext`: quietly tell the model what the user did, for later turns.
 * Hosts advertise which of these they support; see `hostSupport`.
 *
 * The view also follows the host's context (`ui/initialize` result, then
 * `ui/notifications/host-context-changed`): theme, style variables and fonts
 * go onto <html> (see global.css for how our tokens use them), safe-area
 * insets become padding, and the current / available display modes drive the
 * fullscreen toggle.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useApp, useHostStyles } from "@modelcontextprotocol/ext-apps/react";
import type { App, McpUiDisplayMode, McpUiHostContext } from "@modelcontextprotocol/ext-apps";
import type { CallToolResult } from "@modelcontextprotocol/client";
import type {
  GroceryListData,
  MacroSetterData,
  MacroTarget,
  RecipeSelectorData,
  WeeklyCalendarData,
} from "./types.ts";

export type { App, CallToolResult, McpUiDisplayMode };

/** What the connected host lets this view do. Missing support hides the matching buttons. */
export interface HostSupport {
  /** tools/call proxied to the MCP server. */
  serverTools: boolean;
  /** ui/message: add a user message to the conversation. */
  message: boolean;
  /** ui/update-model-context: set context for the model's next turn. */
  modelContext: boolean;
}

/** Fullscreen toggle state, offered only when both the view and the host support fullscreen. */
export interface DisplayModeControl {
  isFullscreen: boolean;
  /** Ask the host to switch between inline and fullscreen; resolves to the mode it set. */
  toggleFullscreen: () => Promise<string>;
}

/** A connected view with its current payload. */
export interface ConnectedView<T> {
  app: App;
  data: T;
  host: HostSupport;
  /** Undefined when fullscreen isn't available (view didn't declare it, or the host lacks it). */
  display: DisplayModeControl | undefined;
  /** Re-render from another tool result (e.g. a refresh via callServerTool). */
  applyResult: (result: CallToolResult) => void;
}

export type McpViewState<T> =
  | { status: "connecting" }
  | { status: "error"; message: string }
  | { status: "waiting"; app: App }
  | ({ status: "ready" } & ConnectedView<T>);

/** Narrows a tool result's structuredContent to a view payload, or null if it doesn't fit. */
export type PayloadParser<T> = (structuredContent: unknown) => T | null;

function firstText(result: CallToolResult): string | null {
  for (const block of result.content) {
    if (block.type === "text") return block.text;
  }
  return null;
}

export function hostSupport(app: App): HostSupport {
  const caps = app.getHostCapabilities();
  return {
    serverTools: caps?.serverTools !== undefined,
    message: caps?.message !== undefined,
    modelContext: caps?.updateModelContext !== undefined,
  };
}

const SAFE_AREA_SIDES = ["top", "right", "bottom", "left"] as const;

/** Expose the host's safe-area insets as --safe-area-* (used by the .mcp-view padding). */
function useSafeAreaInsets(insets: McpUiHostContext["safeAreaInsets"]): void {
  const { top = 0, right = 0, bottom = 0, left = 0 } = insets ?? {};
  useEffect(() => {
    const values = { top, right, bottom, left };
    const root = document.documentElement.style;
    for (const side of SAFE_AREA_SIDES) root.setProperty(`--safe-area-${side}`, `${values[side]}px`);
  }, [top, right, bottom, left]);
}

/**
 * Create and connect an ext-apps `App`, track the latest tool result, and
 * apply the host context.
 *
 * `displayModes` are the modes this view supports (declared to the host as
 * app capabilities); include "fullscreen" to get a `display` control.
 *
 * The tool-result and host-context handlers are registered in `onAppCreated`,
 * i.e. before `connect()`, so nothing the host sends right after the
 * handshake is missed.
 */
export function useMcpView<T>(
  appName: string,
  parse: PayloadParser<T>,
  displayModes: McpUiDisplayMode[] = ["inline"],
): McpViewState<T> {
  const [data, setData] = useState<T | null>(null);
  const [resultError, setResultError] = useState<string | null>(null);
  // Snapshot of app.getHostContext(), refreshed on every host-context change.
  const [hostContext, setHostContext] = useState<McpUiHostContext | undefined>(undefined);

  // Read the parser through a ref so applyResult stays stable across renders.
  const parseRef = useRef(parse);
  parseRef.current = parse;

  const applyResult = useCallback((result: CallToolResult) => {
    if (result.isError) {
      setResultError(firstText(result) ?? "The tool call failed.");
      return;
    }
    const parsed = parseRef.current(result.structuredContent);
    if (parsed === null) {
      setResultError("The tool result did not include the data this view needs.");
      return;
    }
    setResultError(null);
    setData(parsed);
  }, []);

  const { app, isConnected, error } = useApp({
    appInfo: { name: appName, version: "0.1.0" },
    capabilities: { availableDisplayModes: displayModes },
    onAppCreated: (created) => {
      created.ontoolresult = applyResult;
      created.ontoolcancelled = () => {
        setResultError("The tool call was cancelled.");
      };
      // The SDK merges the (partial) change into getHostContext() before this runs.
      created.addEventListener("hostcontextchanged", () => {
        setHostContext({ ...created.getHostContext() });
      });
    },
  });

  // The initial context arrives with the ui/initialize result.
  useEffect(() => {
    if (app && isConnected) setHostContext({ ...app.getHostContext() });
  }, [app, isConnected]);

  // Theme (data-theme + color-scheme), style variables and fonts, now and on change.
  useHostStyles(app, hostContext);
  useSafeAreaInsets(hostContext?.safeAreaInsets);

  const isFullscreen = hostContext?.displayMode === "fullscreen";
  const canFullscreen =
    displayModes.includes("fullscreen") &&
    (hostContext?.availableDisplayModes?.includes("fullscreen") ?? false);

  const toggleFullscreen = useCallback(async () => {
    if (!app) throw new Error("Not connected to the host.");
    const { mode } = await app.requestDisplayMode({ mode: isFullscreen ? "inline" : "fullscreen" });
    // The host answers with the mode it actually set; reflect it right away.
    setHostContext((ctx) => ({ ...ctx, displayMode: mode }));
    return mode;
  }, [app, isFullscreen]);

  if (error) return { status: "error", message: `Couldn't connect to the MCP host: ${error.message}` };
  if (!app || !isConnected) return { status: "connecting" };
  if (resultError) return { status: "error", message: resultError };
  if (data === null) return { status: "waiting", app };
  // Keep the toggle while fullscreen so the user can always get back.
  const display = canFullscreen || isFullscreen ? { isFullscreen, toggleFullscreen } : undefined;
  return { status: "ready", app, data, host: hostSupport(app), display, applyResult };
}

/* ── Actions ─────────────────────────────────────────────────────────────
 * Each helper resolves on success and throws an Error with a readable
 * message otherwise, so pages can show it next to the button. */

/** Call a server tool through the host. Throws on transport errors and error results. */
export async function callServerTool(
  app: App,
  name: string,
  args: Record<string, unknown>,
): Promise<CallToolResult> {
  const result = await app.callServerTool({ name, arguments: args });
  if (result.isError) throw new Error(firstText(result) ?? `${name} failed.`);
  return result;
}

/** Add a user message to the conversation, prompting a model response. */
export async function sendUserMessage(app: App, text: string): Promise<void> {
  const result = await app.sendMessage({ role: "user", content: [{ type: "text", text }] });
  if (result.isError) throw new Error("The host didn't accept the message.");
}

/**
 * Replace the model context this view contributes (each call overwrites the
 * previous one). Structured content is only sent to hosts that accept it.
 */
export async function setModelContext(
  app: App,
  text: string,
  structuredContent?: Record<string, unknown>,
): Promise<void> {
  const accepts = app.getHostCapabilities()?.updateModelContext;
  await app.updateModelContext({
    content: [{ type: "text", text }],
    ...(structuredContent && accepts?.structuredContent ? { structuredContent } : {}),
  });
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
  if (!isRecord(value) || typeof value.member_id !== "string") return null;
  const targets = value.current_targets;
  if (targets !== null && targets !== undefined) {
    if (!isRecord(targets) || typeof targets.protein_g !== "number") return null;
  }
  return value as unknown as MacroSetterData;
};

/** structuredContent of set_macro_target (a MacroTargetSchema). */
export const parseMacroTarget: PayloadParser<MacroTarget> = (value) => {
  if (!isRecord(value) || typeof value.id !== "string") return null;
  if (typeof value.name !== "string" || typeof value.calories !== "number") return null;
  return value as unknown as MacroTarget;
};

export const parseRecipeSelectorData: PayloadParser<RecipeSelectorData> = (value) => {
  if (!isRecord(value) || !Array.isArray(value.recipes)) return null;
  return value as unknown as RecipeSelectorData;
};

export const parseWeeklyCalendarData: PayloadParser<WeeklyCalendarData> = (value) => {
  if (!isRecord(value) || typeof value.plan_id !== "string") return null;
  if (!isRecord(value.plan_summary) || !Array.isArray(value.recipes)) return null;
  return value as unknown as WeeklyCalendarData;
};

export const parseGroceryListData: PayloadParser<GroceryListData> = (value) => {
  if (!isRecord(value) || !isRecord(value.grocery_list)) return null;
  if (!Array.isArray(value.grocery_list.items)) return null;
  return value as unknown as GroceryListData;
};
