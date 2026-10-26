import { useCallback, useState } from "react";
import type { ActionState } from "./types.ts";

/** Runs an action and returns the success message to show. */
export type ActionRunner = (pending: string, run: () => Promise<string>) => void;

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

/**
 * Track one button action at a time: pending → done (with the message the
 * action resolves to) or error (with the thrown message).
 */
export function useAsyncAction(): [ActionState, ActionRunner] {
  const [state, setState] = useState<ActionState>({ kind: "idle" });

  const run = useCallback<ActionRunner>((pending, action) => {
    setState({ kind: "pending", message: pending });
    action().then(
      (message) => setState({ kind: "done", message }),
      (err: unknown) => setState({ kind: "error", message: errorMessage(err) }),
    );
  }, []);

  return [state, run];
}
