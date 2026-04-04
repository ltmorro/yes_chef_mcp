import type { MacroSummary } from "../../types";
import styles from "./MacroBadge.module.css";

type MacroType = "protein" | "carbs" | "fat" | "calories";

interface MacroBadgeProps {
  label: string;
  value: number;
  unit?: string;
  macro: MacroType;
}

export function MacroBadge({ label, value, unit = "g", macro }: MacroBadgeProps) {
  return (
    <div className={`${styles.badge} ${styles[macro]}`}>
      <span className={styles.label}>{label}</span>
      <span className={styles.value}>
        {Math.round(value)}
        {unit}
      </span>
    </div>
  );
}

interface MacroBadgeRowProps {
  macros: MacroSummary;
  className?: string;
}

export function MacroBadgeRow({ macros, className }: MacroBadgeRowProps) {
  return (
    <div className={`${styles.row} ${className ?? ""}`}>
      <MacroBadge label="Cal" value={macros.calories} unit="" macro="calories" />
      <MacroBadge label="P" value={macros.protein_g} macro="protein" />
      <MacroBadge label="C" value={macros.carbs_g} macro="carbs" />
      <MacroBadge label="F" value={macros.fat_g} macro="fat" />
    </div>
  );
}
