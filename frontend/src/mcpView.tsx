/**
 * Mount helper shared by the four MCP view entries.
 *
 * Connects to the host, waits for the show_* tool result, and renders the
 * shared page component with that payload. Connection and payload problems
 * render a visible error instead of an empty page.
 */

import { StrictMode } from "react";
import type { ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { useMcpView } from "./bridge.ts";
import type { ConnectedView, McpUiDisplayMode, PayloadParser } from "./bridge.ts";
import { ViewStatus } from "./components";
import "./global.css";

interface McpViewProps<T> {
  appName: string;
  parse: PayloadParser<T>;
  render: (view: ConnectedView<T>) => ReactNode;
  /** Display modes the view supports; defaults to inline only. */
  displayModes?: McpUiDisplayMode[];
}

function ConnectedMcpView<T>({ appName, parse, render, displayModes }: McpViewProps<T>) {
  const state = useMcpView(appName, parse, displayModes);

  switch (state.status) {
    case "connecting":
      return <ViewStatus title="Connecting to host…" />;
    case "error":
      return <ViewStatus tone="error" title="Something went wrong" message={state.message} />;
    case "waiting":
      return <ViewStatus title="Waiting for data…" />;
    case "ready":
      return <>{render(state)}</>;
  }
}

function McpView<T>(props: McpViewProps<T>) {
  // Not in an iframe: there is no host to talk to, so don't wait for a timeout.
  if (window.parent === window) {
    return (
      <ViewStatus
        tone="error"
        title="Not running inside an MCP host"
        message="Open this view from an MCP client that supports MCP Apps, or use the web app at /api/views/app."
      />
    );
  }
  return <ConnectedMcpView {...props} />;
}

export function mountMcpView<T>(props: McpViewProps<T>): void {
  const root = document.getElementById("root");
  if (!root) throw new Error("Missing #root element");
  createRoot(root).render(
    <StrictMode>
      <div className="mcp-view">
        <McpView {...props} />
      </div>
    </StrictMode>,
  );
}
