import { useState } from "react";
import type { DisplayModeControl } from "../../bridge.ts";
import { Button } from "../Button";

export interface FullscreenToggleProps {
  display: DisplayModeControl;
}

/**
 * Switches an MCP view between inline and fullscreen via the host
 * (ui/request-display-mode). The label reflects the current display mode.
 */
export function FullscreenToggle({ display }: FullscreenToggleProps) {
  const [pending, setPending] = useState(false);

  const toggle = () => {
    setPending(true);
    display
      .toggleFullscreen()
      // Nothing for the user to fix if the host refuses; the view stays as it was.
      .catch((err: unknown) => console.warn("requestDisplayMode failed:", err))
      .finally(() => setPending(false));
  };

  return (
    <Button variant="secondary" size="sm" isDisabled={pending} onPress={toggle}>
      {display.isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
    </Button>
  );
}
