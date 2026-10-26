import { useEffect, useRef, useState } from "react";
import {
  Dialog,
  DialogTrigger,
  Heading,
  Modal,
  ModalOverlay,
  ToggleButton,
  ToggleButtonGroup,
} from "react-aria-components";
import type { Key } from "react-aria-components";
import { ActionStatus, Button, Card, FullscreenToggle, TimerChip } from "../components";
import type { DisplayModeControl } from "../bridge.ts";
import type { CookModeData, CookRating, Ingredient } from "../types.ts";
import { useAsyncAction } from "../useAsyncAction.ts";
import styles from "./CookModePage.module.css";

/* ── Data source ─────────────────────────────────────────────────────── */

export interface CookModeSource {
  data: CookModeData;
  /**
   * Log the meal as cooked and resolve to the message to show. Omitted when
   * the host can't call server tools.
   */
  finish?: (rating: CookRating | null) => Promise<string>;
  /** Fullscreen control; undefined when the host can't go fullscreen. */
  display?: DisplayModeControl;
}

const RATINGS: { id: CookRating; label: string }[] = [
  { id: "good", label: "🙂 Good" },
  { id: "okay", label: "😐 Okay" },
  { id: "bad", label: "🙁 Not great" },
];

function isRating(key: Key): key is CookRating {
  return RATINGS.some((r) => r.id === key);
}

function formatIngredient({ name, quantity, unit }: Ingredient): string {
  if (quantity === null) return name;
  return `${quantity}${unit ? ` ${unit}` : ""} ${name}`;
}

function servingsLabel(servings: number): string {
  return `${servings} ${servings === 1 ? "serving" : "servings"}`;
}

/* ── Ingredient sheet ────────────────────────────────────────────────── */

interface IngredientSheetProps {
  data: CookModeData;
}

function IngredientSheet({ data }: IngredientSheetProps) {
  return (
    <DialogTrigger>
      <Button variant="secondary">Ingredients ({data.ingredients.length})</Button>
      <ModalOverlay className={styles.overlay} isDismissable>
        <Modal className={styles.sheet}>
          <Dialog aria-label="Ingredients" className={styles.dialog}>
            {({ close }) => (
              <>
                <Heading slot="title" className={styles.sheetTitle}>
                  Ingredients · {servingsLabel(data.servings)}
                </Heading>
                <ul className={styles.ingredients}>
                  {data.ingredients.map((ing, i) => (
                    <li key={i}>{formatIngredient(ing)}</li>
                  ))}
                </ul>
                <Button onPress={close}>Close</Button>
              </>
            )}
          </Dialog>
        </Modal>
      </ModalOverlay>
    </DialogTrigger>
  );
}

/* ── Page Component ──────────────────────────────────────────────────── */

interface CookModePageProps {
  source: CookModeSource;
}

export function CookModePage({ source }: CookModePageProps) {
  const { data, finish, display } = source;
  const { steps } = data;
  // steps.length is the "All done" screen after the last step.
  const [current, setCurrent] = useState(0);
  const [rating, setRating] = useState<CookRating | null>(null);
  const [finishState, runFinish] = useAsyncAction();

  // A new recipe starts over at step 1.
  useEffect(() => {
    setCurrent(0);
    setRating(null);
  }, [data]);

  // Cooking wants the whole screen: ask once, and keep the toggle if the host says no.
  const askedFullscreen = useRef(false);
  useEffect(() => {
    if (!display || display.isFullscreen || askedFullscreen.current) return;
    askedFullscreen.current = true;
    display.toggleFullscreen().catch((err: unknown) => console.warn("fullscreen refused:", err));
  }, [display]);

  const isDone = current === steps.length;
  const logged = finishState.kind === "done";
  const progress = isDone ? "All done" : `Step ${current + 1} of ${steps.length}`;

  const handleFinish = () => {
    if (finish) runFinish("Logging…", () => finish(rating));
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className="view-header">
          <h1>{data.recipe_name}</h1>
          <p>
            {servingsLabel(data.servings)} · {progress}
          </p>
        </div>
        <div className={styles.tools}>
          <IngredientSheet data={data} />
          {display && <FullscreenToggle display={display} />}
        </div>
      </div>

      {/* Every step stays mounted so a running timer keeps going on later steps. */}
      {steps.map((step, i) => (
        <div key={step.index} hidden={i !== current}>
          <Card
            pretitle={`Step ${step.index} of ${steps.length}`}
            body={<p className={styles.stepText}>{step.text}</p>}
            footer={step.timer_seconds ? <TimerChip seconds={step.timer_seconds} /> : undefined}
          />
        </div>
      ))}

      {isDone && (
        <Card
          title="All done!"
          subtitle={
            steps.length === 0 ? "This recipe has no written steps." : "How did it turn out?"
          }
          body={
            <ToggleButtonGroup
              aria-label="Rating"
              className={styles.ratings}
              selectionMode="single"
              selectedKeys={rating ? [rating] : []}
              isDisabled={logged}
              onSelectionChange={(keys) => {
                const [key] = [...keys];
                setRating(key !== undefined && isRating(key) ? key : null);
              }}
            >
              {RATINGS.map((r) => (
                <ToggleButton key={r.id} id={r.id} className={styles.rating}>
                  {r.label}
                </ToggleButton>
              ))}
            </ToggleButtonGroup>
          }
          footer={
            finish && (
              <Button
                size="lg"
                onPress={handleFinish}
                isDisabled={logged || finishState.kind === "pending"}
              >
                Done
              </Button>
            )
          }
        />
      )}
      <ActionStatus state={finishState} />

      <div className={styles.nav}>
        <Button
          variant="secondary"
          size="lg"
          isDisabled={current === 0}
          onPress={() => setCurrent((c) => c - 1)}
        >
          Back
        </Button>
        {!isDone && (
          <Button size="lg" onPress={() => setCurrent((c) => c + 1)}>
            {current === steps.length - 1 ? "Finish" : "Next"}
          </Button>
        )}
      </div>
    </div>
  );
}
