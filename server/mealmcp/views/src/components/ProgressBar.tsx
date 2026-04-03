import type { CSSProperties } from "react";
import { colors, radius, spacing } from "../theme";

interface ProgressBarProps {
  value: number;
  max: number;
  color: string;
  label?: string;
  style?: CSSProperties;
}

export function ProgressBar({ value, max, color, label, style }: ProgressBarProps) {
  const pct = max > 0 ? Math.min((value / max) * 100, 150) : 0;
  const isOver = pct > 105;

  return (
    <div style={style}>
      {label && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: "0.75rem",
            marginBottom: spacing.xs,
          }}
        >
          <span style={{ color: colors.textMuted }}>{label}</span>
          <span style={{ color: isOver ? colors.danger : color }}>
            {Math.round(value)} / {Math.round(max)}
          </span>
        </div>
      )}
      <div
        style={{
          height: "6px",
          background: colors.border,
          borderRadius: radius.full,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${Math.min(pct, 100)}%`,
            height: "100%",
            background: isOver ? colors.danger : color,
            borderRadius: radius.full,
            transition: "width 0.3s ease",
          }}
        />
      </div>
    </div>
  );
}
