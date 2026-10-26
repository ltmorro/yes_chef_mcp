/**
 * Build each MCP Apps view as its own single-file HTML bundle.
 *
 * vite-plugin-singlefile only supports one HTML entry per build, so we run
 * one Vite build per view. See vite.config.ts for the per-view config.
 */
import { build } from "vite";

const VIEWS = ["macro-setter", "recipe-selector", "weekly-calendar", "grocery-list"];

for (const view of VIEWS) {
  process.env.VIEW = view;
  await build({ logLevel: "warn" });
  console.log(`built dist/views/${view}.html`);
}
