import type { ActionState } from "../../types.ts";
import styles from "./ActionStatus.module.css";

interface ActionStatusProps {
  state: ActionState;
}

export type { ActionStatusProps };

const TONE_CLASS: Record<ActionState["kind"], string | undefined> = {
  idle: undefined,
  pending: styles.pending,
  done: styles.done,
  error: styles.error,
};

const PREFIX: Record<ActionState["kind"], string> = {
  idle: "",
  pending: "",
  done: "",
  error: "Error: ",
};

/**
 * One-line result of a button action. Always occupies its line so a message
 * appearing never shifts the layout; errors are announced assertively.
 */
export function ActionStatus({ state }: ActionStatusProps) {
  const text = state.kind === "idle" ? "" : `${PREFIX[state.kind]}${state.message}`;
  return (
    <div
      role={state.kind === "error" ? "alert" : "status"}
      className={[styles.status, TONE_CLASS[state.kind]].filter(Boolean).join(" ")}
    >
      {text}
    </div>
  );
}
