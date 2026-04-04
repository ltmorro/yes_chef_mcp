import styles from "./ProgressBar.module.css";

type MacroType = "protein" | "carbs" | "fat" | "calories";

interface ProgressBarProps {
  value: number;
  max: number;
  macro: MacroType;
  label?: string;
  className?: string;
}

export function ProgressBar({ value, max, macro, label, className }: ProgressBarProps) {
  const pct = max > 0 ? Math.min((value / max) * 100, 150) : 0;
  const isOver = pct > 105;

  const classes = [
    styles.wrapper,
    styles[macro],
    isOver ? styles.over : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={classes}>
      {label && (
        <div className={styles.header}>
          <span className={styles.headerLabel}>{label}</span>
          <span className={styles.headerValue}>
            {Math.round(value)} / {Math.round(max)}
          </span>
        </div>
      )}
      <div className={styles.track}>
        <div
          className={styles.fill}
          /* CSS custom property for dynamic width — not an inline style override */
          {...{ style: { "--progress-pct": `${Math.min(pct, 100)}%` } as React.CSSProperties }}
        />
      </div>
    </div>
  );
}
