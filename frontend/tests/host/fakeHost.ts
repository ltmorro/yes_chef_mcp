/**
 * A fake MCP Apps host for Playwright.
 *
 * `openView` loads a built view (dist/views/<name>.html, served by vite
 * preview) into an iframe on a fake host page, then plays the host side of
 * the protocol over postMessage:
 *
 * - answers `ui/initialize` with the configured host capabilities and context;
 * - sends the configured tool result after `ui/notifications/initialized`;
 * - answers `tools/call`, `ui/message`, `ui/update-model-context` and
 *   `ui/request-display-mode` as configured (success or JSON-RPC error);
 * - records every message the view sends, for assertions.
 *
 * The view comes from vite preview on `localhost`; the host page is served by
 * `page.route` on `127.0.0.1` (same port), a different origin, so the view runs
 * cross-origin like in a real host. (A public made-up origin would trip
 * Chromium's local network access checks.) Anything else is aborted.
 */

import { expect, test as base } from "@playwright/test";
import type { FrameLocator, Page } from "@playwright/test";
import type { McpUiHostCapabilities, McpUiHostContext } from "@modelcontextprotocol/ext-apps";

export type ViewName =
  | "macro-setter"
  | "recipe-selector"
  | "weekly-calendar"
  | "grocery-list"
  | "cook-mode";

/** A CallToolResult as the host forwards it (the fixtures' JSON shape). */
export interface ToolResult {
  content: { type: string; text?: string }[];
  structuredContent?: Record<string, unknown>;
  isError?: boolean;
}

/** How the host answers a view request: "ok", or a JSON-RPC error with this message. */
export type Reply = "ok" | { error: string };

/** How the host answers ui/request-display-mode. */
export type DisplayModeReply =
  | "grant" // set the requested mode (and send host-context-changed)
  | { error: string } // reject the request
  | { mode: "inline" | "fullscreen" | "pip" }; // answer with this mode regardless

type StyleVariables = NonNullable<NonNullable<McpUiHostContext["styles"]>["variables"]>;

/** Host context; style variables may be partial, as real hosts send them. */
export type HostContext = Omit<McpUiHostContext, "styles"> & {
  styles?: { variables?: Partial<StyleVariables> };
};

export interface HostConfig {
  toolResult: ToolResult;
  capabilities?: McpUiHostCapabilities;
  hostContext?: HostContext;
  /** tools/call replies by tool name; unknown tools get an isError result. */
  tools?: Record<string, ToolResult | { error: string }>;
  message?: Reply;
  modelContext?: Reply;
  displayMode?: DisplayModeReply;
}

/** One JSON-RPC message the view sent to the host. */
export interface ViewMessage {
  id?: number | string;
  method: string;
  params: Record<string, unknown>;
}

/** Everything a host with full support advertises. */
export const FULL_CAPS: McpUiHostCapabilities = {
  serverTools: {},
  message: { text: {} },
  updateModelContext: { text: {}, structuredContent: {} },
};

const HOST_PAGE = `<!doctype html><html><head><meta charset="utf-8"></head>
<body><iframe id="view" title="view" width="1000" height="1400"></iframe></body></html>`;

const LOCAL_HOSTS = ["localhost", "127.0.0.1"];

/** Playwright `test` that blocks every request leaving this machine. */
export const test = base.extend({
  page: async ({ page }, use) => {
    await page.route(
      (url) => !LOCAL_HOSTS.includes(url.hostname),
      (route) => route.abort(),
    );
    await use(page);
  },
});

export { expect };

/** Runs inside the host page: the whole host side of the protocol. */
function installHost(args: { config: Required<HostConfig>; viewUrl: string }): void {
  const { config, viewUrl } = args;
  const iframe = document.getElementById("view");
  if (!(iframe instanceof HTMLIFrameElement)) throw new Error("missing #view iframe");
  const log: unknown[] = [];
  Object.assign(window, { __hostLog: log });

  const send = (message: object) =>
    iframe.contentWindow?.postMessage({ jsonrpc: "2.0", ...message }, "*");
  const notify = (method: string, params: object) => send({ method, params });
  Object.assign(window, { __notify: notify });

  const answer = (id: unknown, reply: Reply, result: object = {}) =>
    send(reply === "ok" ? { id, result } : { id, error: { code: -32000, message: reply.error } });

  window.addEventListener("message", (event) => {
    if (event.source !== iframe.contentWindow) return;
    const msg: { id?: unknown; method?: string; params?: Record<string, unknown> } = event.data;
    if (!msg.method) return; // a response to something we sent
    log.push({ id: msg.id, method: msg.method, params: msg.params ?? {} });

    switch (msg.method) {
      case "ui/initialize":
        return answer(msg.id, "ok", {
          protocolVersion: "2026-01-26",
          hostInfo: { name: "fake-host", version: "0.0.1" },
          hostCapabilities: config.capabilities,
          hostContext: config.hostContext,
        });
      case "ui/notifications/initialized":
        return notify("ui/notifications/tool-result", config.toolResult);
      case "tools/call": {
        const name = String(msg.params?.name);
        const reply = config.tools[name] ?? {
          isError: true,
          content: [{ type: "text", text: `Unknown tool: ${name}` }],
        };
        return "error" in reply ? answer(msg.id, reply) : answer(msg.id, "ok", reply);
      }
      case "ui/message":
        return answer(msg.id, config.message);
      case "ui/update-model-context":
        return answer(msg.id, config.modelContext);
      case "ui/request-display-mode": {
        const reply = config.displayMode;
        if (reply === "grant") {
          const mode = msg.params?.mode;
          answer(msg.id, "ok", { mode });
          return notify("ui/notifications/host-context-changed", { displayMode: mode });
        }
        return "error" in reply ? answer(msg.id, reply) : answer(msg.id, "ok", reply);
      }
      default:
        // Any other request (e.g. ui/open-link): accept it.
        if (msg.id !== undefined) answer(msg.id, "ok");
    }
  });

  iframe.src = viewUrl;
}

export interface FakeHost {
  page: Page;
  /** The view's document. */
  view: FrameLocator;
  /** Messages the view sent, in order, optionally only those with this method. */
  messages: (method?: string) => Promise<ViewMessage[]>;
  /** Wait for (and return) the first message with this method sent after the last clear. */
  waitFor: (method: string) => Promise<ViewMessage>;
  clearMessages: () => Promise<void>;
  /** Send a host notification (e.g. ui/notifications/host-context-changed). */
  notify: (method: string, params: object) => Promise<void>;
  /** Uncaught errors in the page or the view. */
  errors: string[];
}

function isViewMessage(value: unknown): value is ViewMessage {
  return typeof value === "object" && value !== null && "method" in value && "params" in value;
}

export async function openView(page: Page, view: ViewName, config: HostConfig): Promise<FakeHost> {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(String(err)));

  // vite preview serves dist/ under the SPA base, so the views are at /views/static/views/.
  const viewUrl = new URL(`/views/static/views/${view}.html`, test.info().project.use.baseURL);
  const hostUrl = new URL("/__fake-host", viewUrl);
  hostUrl.hostname = "127.0.0.1";
  await page.route(hostUrl.href, (route) =>
    route.fulfill({ contentType: "text/html", body: HOST_PAGE }),
  );
  await page.goto(hostUrl.href);

  const full: Required<HostConfig> = {
    capabilities: FULL_CAPS,
    hostContext: { theme: "light" },
    tools: {},
    message: "ok",
    modelContext: "ok",
    displayMode: "grant",
    ...config,
  };
  await page.evaluate(installHost, { config: full, viewUrl: viewUrl.href });

  const messages = async (method?: string): Promise<ViewMessage[]> => {
    const log: unknown = await page.evaluate("window.__hostLog");
    const all = Array.isArray(log) ? log.filter(isViewMessage) : [];
    return method ? all.filter((m) => m.method === method) : all;
  };

  const waitFor = async (method: string): Promise<ViewMessage> => {
    await expect.poll(async () => (await messages(method)).length).toBeGreaterThan(0);
    const [first] = await messages(method);
    if (!first) throw new Error(`no ${method} message`);
    return first;
  };

  const host: FakeHost = {
    page,
    view: page.frameLocator("#view"),
    messages,
    waitFor,
    clearMessages: () => page.evaluate("window.__hostLog.length = 0").then(() => undefined),
    notify: (method, params) =>
      page.evaluate(
        ({ name, json }) => {
          const send: unknown = Reflect.get(window, "__notify");
          if (typeof send === "function") send(name, JSON.parse(json));
        },
        { name: method, json: JSON.stringify(params) },
      ),
    errors,
  };
  await waitFor("ui/notifications/initialized");
  return host;
}

/** The first text block of a ui/message or ui/update-model-context message. */
export function textOf(message: ViewMessage): string {
  const content = message.params.content;
  if (!Array.isArray(content)) return "";
  const block: unknown = content[0];
  if (typeof block !== "object" || block === null || !("text" in block)) return "";
  return typeof block.text === "string" ? block.text : "";
}

/** A tools/call message's tool name and arguments (without protocol extras like _meta). */
export function toolCall(message: ViewMessage | undefined): { name: unknown; arguments: unknown } {
  return { name: message?.params.name, arguments: message?.params.arguments };
}
