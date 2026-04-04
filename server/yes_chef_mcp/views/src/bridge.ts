/**
 * MCP Apps bridge: communication between view components and the MCP host.
 *
 * Uses the official @modelcontextprotocol/ext-apps SDK when running inside
 * an MCP host iframe. Falls back to reading <script id="view-data"> and
 * dispatching DOM events for standalone FastAPI usage.
 */

// Re-export the App type for consumers that need it directly
export type { McpApp };

interface TextContent {
  type: "text";
  text: string;
}

interface ToolResultPayload {
  content?: Array<TextContent | { type: string }>;
}

interface McpApp {
  ontoolresult: ((result: ToolResultPayload) => void) | null;
  callServerTool: (params: { name: string; arguments: Record<string, unknown> }) => Promise<unknown>;
  connect: () => Promise<void>;
}

/** Singleton app instance — lazily initialized by connectApp(). */
let appInstance: McpApp | null = null;

/**
 * Connect to the MCP host via the ext-apps SDK.
 *
 * In MCP context: establishes postMessage channel with the host iframe.
 * In standalone FastAPI mode: returns null (use getViewData() instead).
 */
export async function connectApp(name: string): Promise<McpApp | null> {
  if (appInstance) return appInstance;

  try {
    // Dynamic import — the SDK is loaded from CDN in the HTML entry points.
    // This will fail gracefully in standalone FastAPI mode.
    const mod = await import(
      // @ts-expect-error CDN import, not in node_modules
      "https://unpkg.com/@modelcontextprotocol/ext-apps@0.4.0/app-with-deps"
    );
    const App = mod.App as new (opts: { name: string; version: string }) => McpApp;
    appInstance = new App({ name, version: "0.1.0" });
    await appInstance.connect();
    return appInstance;
  } catch {
    // Not running inside an MCP host — standalone mode
    return null;
  }
}

/**
 * Call a server-side MCP tool from within the app UI.
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
 * Parse initial data injected by the server into `<script id="view-data">`.
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
export function extractText(result: ToolResultPayload): string | null {
  const text = result.content?.find((c): c is TextContent => c.type === "text");
  return text?.text ?? null;
}
