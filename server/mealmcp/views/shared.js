/**
 * Shared utilities and design tokens for MealMCP view components.
 *
 * Loaded by all HTML view files. Provides:
 * - sendResult() bridge for MCP ↔ LLM communication
 * - Design tokens (colors, spacing, typography)
 * - Reusable React component primitives
 */

/* ── MCP Bridge ──────────────────────────────────────────────────────── */

/**
 * Send structured data back to the LLM orchestrator.
 * In MCP context this posts to the parent frame; in standalone FastAPI
 * mode it dispatches a CustomEvent for the host page to handle.
 */
function sendResult(payload) {
  // FastMCP view tool protocol
  if (window.__FASTMCP_SEND_RESULT__) {
    window.__FASTMCP_SEND_RESULT__(payload);
    return;
  }

  // Fallback: dispatch DOM event for FastAPI / standalone usage
  window.dispatchEvent(
    new CustomEvent("mealmcp:result", { detail: payload })
  );
}

/**
 * Parse initial data injected by the server into a <script id="view-data"> tag.
 * Returns an empty object if no data is present.
 */
function getViewData() {
  const el = document.getElementById("view-data");
  if (!el) return {};
  try {
    return JSON.parse(el.textContent);
  } catch {
    return {};
  }
}

/* ── Design Tokens ───────────────────────────────────────────────────── */

const theme = {
  colors: {
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
  },

  radius: { sm: "6px", md: "10px", lg: "14px", full: "9999px" },
  spacing: { xs: "4px", sm: "8px", md: "16px", lg: "24px", xl: "32px" },
  font: {
    sans: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    mono: "'JetBrains Mono', 'Fira Code', monospace",
  },
};

/* ── Shared Styles (injected as CSS string) ──────────────────────────── */

const sharedCSS = `
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: ${theme.font.sans};
    background: ${theme.colors.bg};
    color: ${theme.colors.text};
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
  }

  .view-container {
    max-width: 960px;
    margin: 0 auto;
    padding: ${theme.spacing.lg};
  }

  .view-header {
    margin-bottom: ${theme.spacing.lg};
  }

  .view-header h1 {
    font-size: 1.5rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: ${theme.colors.text};
  }

  .view-header p {
    font-size: 0.875rem;
    color: ${theme.colors.textMuted};
    margin-top: ${theme.spacing.xs};
  }
`;

/* ── React Primitive Components ──────────────────────────────────────── */

const e = React.createElement;

/** Styled button with variant support. */
function Button({ children, variant = "primary", onClick, disabled, style }) {
  const baseStyle = {
    padding: "10px 20px",
    borderRadius: theme.radius.md,
    border: "1px solid transparent",
    fontSize: "0.875rem",
    fontWeight: 600,
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.5 : 1,
    transition: "all 0.15s ease",
    fontFamily: theme.font.sans,
    ...style,
  };

  const variants = {
    primary: {
      background: theme.colors.primary,
      color: "#fff",
      borderColor: theme.colors.primary,
    },
    secondary: {
      background: "transparent",
      color: theme.colors.text,
      borderColor: theme.colors.border,
    },
    danger: {
      background: theme.colors.dangerBg,
      color: theme.colors.danger,
      borderColor: "transparent",
    },
    ghost: {
      background: "transparent",
      color: theme.colors.textMuted,
      borderColor: "transparent",
    },
  };

  return e("button", {
    style: { ...baseStyle, ...variants[variant] },
    onClick,
    disabled,
  }, children);
}

/** Card container with subtle border. */
function Card({ children, style, onClick }) {
  return e("div", {
    style: {
      background: theme.colors.surface,
      border: `1px solid ${theme.colors.border}`,
      borderRadius: theme.radius.lg,
      padding: theme.spacing.lg,
      cursor: onClick ? "pointer" : "default",
      transition: "border-color 0.15s ease",
      ...style,
    },
    onClick,
  }, children);
}

/** Macro badge showing a single nutrient value. */
function MacroBadge({ label, value, unit = "g", color }) {
  return e("div", {
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: theme.spacing.xs,
      padding: `${theme.spacing.xs} ${theme.spacing.sm}`,
      background: `${color}18`,
      borderRadius: theme.radius.full,
      fontSize: "0.75rem",
      fontWeight: 600,
    },
  },
    e("span", { style: { color: theme.colors.textMuted } }, label),
    e("span", { style: { color } }, `${Math.round(value)}${unit}`)
  );
}

/** Row of macro badges for a full nutrient summary. */
function MacroBadgeRow({ macros, style }) {
  return e("div", {
    style: {
      display: "flex",
      gap: theme.spacing.sm,
      flexWrap: "wrap",
      ...style,
    },
  },
    e(MacroBadge, { label: "Cal", value: macros.calories, unit: "", color: theme.colors.calories }),
    e(MacroBadge, { label: "P", value: macros.protein_g, color: theme.colors.protein }),
    e(MacroBadge, { label: "C", value: macros.carbs_g, color: theme.colors.carbs }),
    e(MacroBadge, { label: "F", value: macros.fat_g, color: theme.colors.fat })
  );
}

/** Horizontal progress bar with label. */
function ProgressBar({ value, max, color, label, style }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 150) : 0;
  const isOver = pct > 105;

  return e("div", { style: { ...style } },
    label && e("div", {
      style: {
        display: "flex",
        justifyContent: "space-between",
        fontSize: "0.75rem",
        marginBottom: theme.spacing.xs,
      },
    },
      e("span", { style: { color: theme.colors.textMuted } }, label),
      e("span", { style: { color: isOver ? theme.colors.danger : color } },
        `${Math.round(value)} / ${Math.round(max)}`)
    ),
    e("div", {
      style: {
        height: "6px",
        background: theme.colors.border,
        borderRadius: theme.radius.full,
        overflow: "hidden",
      },
    },
      e("div", {
        style: {
          width: `${Math.min(pct, 100)}%`,
          height: "100%",
          background: isOver ? theme.colors.danger : color,
          borderRadius: theme.radius.full,
          transition: "width 0.3s ease",
        },
      })
    )
  );
}
