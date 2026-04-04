/**
 * JS-accessible design tokens.
 *
 * These mirror the CSS custom properties in global.css and exist ONLY for
 * contexts where CSS cannot reach (e.g. <canvas> rendering, dynamic SVG).
 * For all other styling, use CSS custom properties via CSS modules.
 */

export const tokens = {
  color: {
    bg: "#0f1117",
    surface: "#1a1d27",
    surfaceHover: "#242836",
    border: "#2e3347",
    borderFocus: "#c2703e",

    text: "#e2e8f0",
    textInverse: "#0f1117",
    textMuted: "#94a3b8",
    textDim: "#64748b",

    primary: "#c2703e",
    primaryHover: "#d4813b",

    success: "#22c55e",
    warning: "#f59e0b",
    danger: "#ef4444",

    protein: "#3b82f6",
    carbs: "#f59e0b",
    fat: "#ef4444",
    calories: "#a78bfa",
  },
  font: {
    brand: "'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    mono: "'JetBrains Mono', 'Fira Code', monospace",
  },
} as const;
