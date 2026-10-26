import type { DisplayModeControl } from "../../bridge.ts";
import { useAsyncAction } from "../../useAsyncAction.ts";
import { ActionStatus } from "../ActionStatus";
import { Button } from "../Button";
import styles from "./FullscreenToggle.module.css";

export interface FullscreenToggleProps {
  display: DisplayModeControl;
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

/**
 * Switches an MCP view between inline and fullscreen via the host
 * (ui/request-display-mode). The label reflects the current display mode;
 * a refused request, or a host that picks another mode, is shown below it.
 */
export function FullscreenToggle({ display }: FullscreenToggleProps) {
  const [state, run] = useAsyncAction();

  const toggle = () => {
    const wanted = display.isFullscreen ? "inline" : "fullscreen";
    run("", async () => {
      const mode = await display.toggleFullscreen().catch((err: unknown) => {
        throw new Error(`Couldn't switch to ${wanted}: ${errorMessage(err)}`);
      });
      return mode === wanted ? "" : `The host kept the view ${mode}.`;
    });
  };

  return (
    <div className={styles.toggle}>
      <Button
        variant="secondary"
        size="sm"
        isDisabled={state.kind === "pending"}
        onPress={toggle}
      >
        {display.isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
      </Button>
      <ActionStatus state={state} />
    </div>
  );
}
