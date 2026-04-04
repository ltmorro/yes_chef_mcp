/**
 * JS-accessible design tokens.
 *
 * These mirror the CSS custom properties in global.css and exist ONLY for
 * contexts where CSS cannot reach (e.g. <canvas> rendering, dynamic SVG).
 * For all other styling, use CSS custom properties via CSS modules.
 */

export const tokens = {
  color: {
    bg: "#F4E9D8",
    surface: "#F2E6D6",
    surfaceHover: "#EDE0CB",
    border: "rgba(45, 58, 46, 0.2)",
    borderFocus: "#D6A21E",

    text: "#2D3A2E",
    textInverse: "#F4E9D8",
    textMuted: "#3C2E2A",
    textDim: "rgba(60, 46, 42, 0.55)",

    primary: "#009B8D",
    primaryHover: "#007A70",

    success: "#5A6B2D",
    warning: "#3C2E2A",   // text on mustard warning backgrounds
    warningBg: "#D6A21E",
    danger: "#C85A3A",

    protein: "#009B8D",
    proteinBg: "rgba(0, 155, 141, 0.10)",
    carbs: "#D6A21E",
    carbsBg: "rgba(214, 162, 30, 0.12)",
    fat: "#C85A3A",
    fatBg: "rgba(200, 90, 58, 0.10)",
    calories: "#5A6B2D",
    caloriesBg: "rgba(90, 107, 45, 0.10)",
  },
  font: {
    brand: "'Lato', sans-serif",
    heading: "'Playfair Display', serif",
    mono: "'Recursive', monospace",
  },
} as const;
