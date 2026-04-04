import type { ReactNode } from "react";
import styles from "./Card.module.css";

interface CardProps {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  selected?: boolean;
}

export function Card({ children, className, onClick, selected }: CardProps) {
  const classes = [
    styles.card,
    onClick ? styles.interactive : "",
    selected ? styles.selected : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={classes} onClick={onClick}>
      {children}
    </div>
  );
}
