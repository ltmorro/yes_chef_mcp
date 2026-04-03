/** Design tokens for MealMCP views. */

export const colors = {
  bg: "#0f1117",
  surface: "#1a1d27",
  surfaceHover: "#242836",
  border: "#2e3347",
  borderFocus: "#6366f1",

  text: "#e2e8f0",
  textMuted: "#94a3b8",
  textDim: "#64748b",

  primary: "#6366f1",
  primaryHover: "#818cf8",
  primaryBg: "rgba(99, 102, 241, 0.12)",

  success: "#22c55e",
  successBg: "rgba(34, 197, 94, 0.12)",
  warning: "#f59e0b",
  warningBg: "rgba(245, 158, 11, 0.12)",
  danger: "#ef4444",
  dangerBg: "rgba(239, 68, 68, 0.12)",

  protein: "#3b82f6",
  carbs: "#f59e0b",
  fat: "#ef4444",
  calories: "#a78bfa",
} as const;

export const radius = {
  sm: "6px",
  md: "10px",
  lg: "14px",
  full: "9999px",
} as const;

export const spacing = {
  xs: "4px",
  sm: "8px",
  md: "16px",
  lg: "24px",
  xl: "32px",
} as const;

export const font = {
  sans: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  mono: "'JetBrains Mono', 'Fira Code', monospace",
} as const;
