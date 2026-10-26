import { resolve } from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

/**
 * Two build flavours share this config:
 *
 * - Default (`vite build`): the SPA (`app.html`) as a normal multi-asset
 *   build in `dist/`, served by FastAPI from `/views/static/`.
 * - `VIEW=<name> vite build`: one MCP Apps view (`<name>.html`) as a single
 *   self-contained HTML file in `dist/views/`, with all JS and CSS inlined.
 *   MCP hosts render it in a sandboxed iframe, so it can't load assets from
 *   our server. `scripts/build-views.mjs` runs this once per view.
 */
const MCP_VIEWS = [
  "macro-setter",
  "recipe-selector",
  "weekly-calendar",
  "grocery-list",
] as const;

export default defineConfig(() => {
  const view = process.env.VIEW;

  if (view) {
    if (!(MCP_VIEWS as readonly string[]).includes(view)) {
      throw new Error(`Unknown VIEW "${view}". Expected one of: ${MCP_VIEWS.join(", ")}`);
    }
    return {
      plugins: [react(), viteSingleFile({ removeViteModuleLoader: true })],
      root: resolve(__dirname),
      build: {
        outDir: resolve(__dirname, "dist/views"),
        emptyOutDir: false,
        rollupOptions: {
          input: resolve(__dirname, `${view}.html`),
          onwarn(warning, defaultHandler) {
            // zod ships @__PURE__ comments Rollup can't place; harmless noise.
            if (warning.code === "INVALID_ANNOTATION") return;
            defaultHandler(warning);
          },
        },
      },
    };
  }

  return {
    plugins: [react()],
    root: resolve(__dirname),
    base: "/views/static/",
    build: {
      outDir: resolve(__dirname, "dist"),
      emptyOutDir: true,
      rollupOptions: {
        input: {
          app: resolve(__dirname, "app.html"),
        },
      },
    },
  };
});
