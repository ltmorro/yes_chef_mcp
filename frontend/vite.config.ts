import { resolve } from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  root: resolve(__dirname),
  base: "/views/static/",
  build: {
    outDir: resolve(__dirname, "dist"),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        "macro-setter": resolve(__dirname, "macro-setter.html"),
        "recipe-selector": resolve(__dirname, "recipe-selector.html"),
        "weekly-calendar": resolve(__dirname, "weekly-calendar.html"),
        "grocery-list": resolve(__dirname, "grocery-list.html"),
      },
    },
  },
});
