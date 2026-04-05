import type { ReactNode } from "react";
import { Button as AriaButton } from "react-aria-components";
import styles from "./Card.module.css";

interface CardProps {
  children?: ReactNode;
  className?: string;
  onPress?: () => void;
  selected?: boolean;
  leadingMedia?: ReactNode;
  pretitle?: ReactNode;
  title?: ReactNode;
  subtitle?: ReactNode;
  trailingMedia?: ReactNode;
  body?: ReactNode;
  footer?: ReactNode;
}

export type { CardProps };

export function Card({
  children,
  className,
  onPress,
  selected,
  leadingMedia,
  pretitle,
  title,
  subtitle,
  trailingMedia,
  body,
  footer,
}: CardProps) {
  const hasSlots = leadingMedia || pretitle || title || subtitle || trailingMedia || body || footer;

  const classes = [
    styles.card,
    hasSlots ? styles.slotted : "",
    leadingMedia ? styles.hasLeading : "",
    onPress ? styles.interactive : "",
    selected ? styles.selected : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const content = hasSlots ? (
    <>
      {leadingMedia && <div className={styles.leadingMedia}>{leadingMedia}</div>}
      <div className={styles.content}>
        {(pretitle || title || subtitle || trailingMedia) && (
          <div className={styles.header}>
            <div className={styles.headerText}>
              {pretitle && <div className={styles.pretitle}>{pretitle}</div>}
              {title && <div className={styles.title}>{title}</div>}
              {subtitle && <div className={styles.subtitle}>{subtitle}</div>}
            </div>
            {trailingMedia && <div className={styles.trailingMedia}>{trailingMedia}</div>}
          </div>
        )}
        {body && <div className={styles.body}>{body}</div>}
        {footer && <div className={styles.footer}>{footer}</div>}
      </div>
    </>
  ) : children;

  if (onPress) {
    return (
      <AriaButton className={classes} onPress={onPress}>
        {content}
      </AriaButton>
    );
  }

  return <div className={classes}>{content}</div>;
}
