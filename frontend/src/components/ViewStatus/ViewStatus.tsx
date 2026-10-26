import { Card } from "../Card";
import styles from "./ViewStatus.module.css";

interface ViewStatusProps {
  /** "error" renders a visible error surface; "info" a muted placeholder. */
  tone?: "info" | "error";
  title: string;
  message?: string;
}

export type { ViewStatusProps };

/** Full-width placeholder for loading, waiting and error states of a view. */
export function ViewStatus({ tone = "info", title, message }: ViewStatusProps) {
  return (
    <div role={tone === "error" ? "alert" : "status"}>
      <Card
        className={tone === "error" ? styles.error : styles.info}
        pretitle={tone === "error" ? "Error" : undefined}
        title={title}
        subtitle={message}
      />
    </div>
  );
}
