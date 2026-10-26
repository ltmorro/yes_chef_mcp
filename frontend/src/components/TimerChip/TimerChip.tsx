import { useEffect, useState } from "react";
import { Button } from "react-aria-components";
import styles from "./TimerChip.module.css";

export interface TimerChipProps {
  seconds: number;
}

/** "1:05:00" for an hour or more, else "5:00". */
function formatClock(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = String(totalSeconds % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

/**
 * A countdown timer chip: press to start, pause, resume, and reset once done.
 *
 * Counts against a wall-clock deadline rather than decrementing per tick, so
 * a throttled background tab (a phone screen turning off) doesn't slow it.
 */
export function TimerChip({ seconds }: TimerChipProps) {
  const [endsAt, setEndsAt] = useState<number | null>(null);
  const [remaining, setRemaining] = useState(seconds);

  useEffect(() => {
    if (endsAt === null) return;
    const tick = () => {
      const left = Math.max(0, Math.ceil((endsAt - Date.now()) / 1000));
      setRemaining(left);
      if (left === 0) setEndsAt(null);
    };
    tick();
    const id = setInterval(tick, 250);
    return () => clearInterval(id);
  }, [endsAt]);

  const running = endsAt !== null;
  const finished = remaining === 0;

  const press = () => {
    if (running) setEndsAt(null);
    else if (finished) setRemaining(seconds);
    else setEndsAt(Date.now() + remaining * 1000);
  };

  let label: string;
  if (finished) label = "⏰ Time's up · Reset";
  else if (running) label = `⏸ Pause · ${formatClock(remaining)}`;
  else if (remaining === seconds) label = `▶ Start timer · ${formatClock(remaining)}`;
  else label = `▶ Resume · ${formatClock(remaining)}`;

  const classes = [styles.chip, running ? styles.running : "", finished ? styles.finished : ""]
    .filter(Boolean)
    .join(" ");

  return (
    <Button className={classes} onPress={press}>
      {label}
    </Button>
  );
}
