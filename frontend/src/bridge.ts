/**
 * MCP Apps bridge: communication between view components and the MCP host.
 *
 * Uses the official @modelcontextprotocol/ext-apps SDK (bundled into each
 * single-file view) when running inside an MCP host iframe. Falls back to
 * reading <script id="view-data"> and dispatching DOM events for standalone
 * FastAPI usage.
 */

import { App } from "@modelcontextprotocol/ext-apps";
import type { CallToolResult } from "@modelcontextprotocol/client";

export type { App as McpApp };

/** Singleton app instance — lazily initialized by connectApp(). */
let appInstance: App | null = null;

/**
 * Connect to the MCP host via the ext-apps SDK.
 *
 * In MCP context: establishes postMessage channel with the host iframe.
 * In standalone FastAPI mode: returns null (use getViewData() instead).
 */
export async function connectApp(name: string): Promise<App | null> {
  if (appInstance) return appInstance;

  try {
    const app = new App({ name, version: "0.1.0" });
    await app.connect();
    appInstance = app;
    return app;
  } catch {
    // Not running inside an MCP host — standalone mode
    return null;
  }
}

/**
 * Call a backend-side MCP tool from within the app UI.
 *
 * In MCP context: routes through the host's postMessage channel.
 * In standalone mode: dispatches a CustomEvent for the host page to handle.
 */
export async function callTool(
  name: string,
  args: Record<string, unknown>,
): Promise<unknown> {
  if (appInstance) {
    return appInstance.callServerTool({ name, arguments: args });
  }

  // Standalone fallback: dispatch DOM event
  const event = new CustomEvent("yes_chef_mcp:tool-call", {
    detail: { name, arguments: args },
  });
  window.dispatchEvent(event);
  return null;
}

/**
 * Parse initial data injected by the backend into `<script id="view-data">`.
 *
 * Used in both MCP and standalone modes. The MCP host also pushes tool
 * results via ontoolresult, but the initial data payload is always
 * available in the script tag for immediate rendering.
 */
export function getViewData<T>(): T {
  const el = document.getElementById("view-data");
  if (!el?.textContent) return {} as T;
  try {
    return JSON.parse(el.textContent) as T;
  } catch {
    return {} as T;
  }
}

/**
 * Extract text content from an MCP tool result payload.
 */
export function extractText(result: Pick<CallToolResult, "content">): string | null {
  for (const block of result.content ?? []) {
    if (block.type === "text") return block.text;
  }
  return null;
}
