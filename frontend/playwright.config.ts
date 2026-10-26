import { defineConfig } from "@playwright/test";

/**
 * Fake MCP host regression tests (tests/host/). Run `npm run build` first:
 * the tests load the built views from `dist/` through `vite preview`.
 *
 * Browser: Playwright's own Chromium (PLAYWRIGHT_BROWSERS_PATH, or its default
 * cache), unless PW_CHROMIUM_PATH points at another Chromium binary.
 */
const PORT = Number(process.env.HOST_TEST_PORT ?? 4319);

export default defineConfig({
  testDir: "tests/host",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: "list",
  timeout: 15_000,
  expect: { timeout: 3_000 },
  use: {
    baseURL: `http://localhost:${PORT}`,
    browserName: "chromium",
    // The fake host page (route-fulfilled, so not a loopback response) embeds
    // the view from localhost; let Chromium's local network access checks allow it.
    permissions: ["local-network-access"],
    launchOptions: {
      executablePath: process.env.PW_CHROMIUM_PATH || undefined,
    },
  },
  webServer: {
    // Serves dist/ under /views/static/ (the SPA's base), views included.
    command: `npx vite preview --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}/views/static/app.html`,
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
