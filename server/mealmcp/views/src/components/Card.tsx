import type { CSSProperties, ReactNode } from "react";
import { colors, radius, spacing } from "../theme";

interface CardProps {
  children: ReactNode;
  style?: CSSProperties;
  onClick?: () => void;
}

export function Card({ children, style, onClick }: CardProps) {
  return (
    <div
      style={{
        background: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.lg,
        padding: spacing.lg,
        cursor: onClick ? "pointer" : "default",
        transition: "border-color 0.15s ease",
        ...style,
      }}
      onClick={onClick}
    >
      {children}
    </div>
  );
}
