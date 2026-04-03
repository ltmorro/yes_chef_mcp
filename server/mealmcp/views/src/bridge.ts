/**
 * MCP bridge: communication between view components and the LLM orchestrator.
 */

declare global {
  interface Window {
    __FASTMCP_SEND_RESULT__?: (payload: unknown) => void;
  }
}

/**
 * Send structured data back to the LLM.
 * In MCP context: posts to the FastMCP parent frame.
 * In standalone FastAPI mode: dispatches a CustomEvent for the host page.
 */
export function sendResult(payload: unknown): void {
  if (window.__FASTMCP_SEND_RESULT__) {
    window.__FASTMCP_SEND_RESULT__(payload);
    return;
  }

  window.dispatchEvent(
    new CustomEvent("mealmcp:result", { detail: payload }),
  );
}

/**
 * Parse initial data injected by the server into `<script id="view-data">`.
 * Returns the parsed object or an empty object if absent/invalid.
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
