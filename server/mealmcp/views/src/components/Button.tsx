import type { CSSProperties, ReactNode } from "react";
import { colors, radius, font } from "../theme";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";

interface ButtonProps {
  children: ReactNode;
  variant?: ButtonVariant;
  onClick?: () => void;
  disabled?: boolean;
  style?: CSSProperties;
}

const variantStyles: Record<ButtonVariant, CSSProperties> = {
  primary: {
    background: colors.primary,
    color: "#fff",
    borderColor: colors.primary,
  },
  secondary: {
    background: "transparent",
    color: colors.text,
    borderColor: colors.border,
  },
  danger: {
    background: colors.dangerBg,
    color: colors.danger,
    borderColor: "transparent",
  },
  ghost: {
    background: "transparent",
    color: colors.textMuted,
    borderColor: "transparent",
  },
};

export function Button({
  children,
  variant = "primary",
  onClick,
  disabled,
  style,
}: ButtonProps) {
  return (
    <button
      style={{
        padding: "10px 20px",
        borderRadius: radius.md,
        border: "1px solid transparent",
        fontSize: "0.875rem",
        fontWeight: 600,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        transition: "all 0.15s ease",
        fontFamily: font.sans,
        ...variantStyles[variant],
        ...style,
      }}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}
