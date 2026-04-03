import type { CSSProperties } from "react";
import { colors, radius, spacing } from "../theme";
import type { MacroSummary } from "../types";

interface MacroBadgeProps {
  label: string;
  value: number;
  unit?: string;
  color: string;
}

export function MacroBadge({ label, value, unit = "g", color }: MacroBadgeProps) {
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: spacing.xs,
        padding: `${spacing.xs} ${spacing.sm}`,
        background: `${color}18`,
        borderRadius: radius.full,
        fontSize: "0.75rem",
        fontWeight: 600,
      }}
    >
      <span style={{ color: colors.textMuted }}>{label}</span>
      <span style={{ color }}>
        {Math.round(value)}
        {unit}
      </span>
    </div>
  );
}

interface MacroBadgeRowProps {
  macros: MacroSummary;
  style?: CSSProperties;
}

export function MacroBadgeRow({ macros, style }: MacroBadgeRowProps) {
  return (
    <div style={{ display: "flex", gap: spacing.sm, flexWrap: "wrap", ...style }}>
      <MacroBadge label="Cal" value={macros.calories} unit="" color={colors.calories} />
      <MacroBadge label="P" value={macros.protein_g} color={colors.protein} />
      <MacroBadge label="C" value={macros.carbs_g} color={colors.carbs} />
      <MacroBadge label="F" value={macros.fat_g} color={colors.fat} />
    </div>
  );
}
